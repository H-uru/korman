#    This file is part of Korman.
#
#    Korman is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Korman is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Korman.  If not, see <http://www.gnu.org/licenses/>.

import bpy
import itertools
from PyHSPlasma import *
from math import fabs
import weakref

from ..exporter.logger import ExportProgressLogger
from . import explosions
from .. import helpers
from . import material
from . import utils

_MAX_VERTS_PER_SPAN = 0xFFFF
_WARN_VERTS_PER_SPAN = 0x8000

_VERTEX_COLOR_LAYERS = {"col", "color", "colour"}

class _GeoSpan:
    def __init__(self, bo, bm, geospan, pass_index=None):
        self.geospan = geospan
        self.pass_index = pass_index if pass_index is not None else 0
        self.mult_color = self._determine_mult_color(bo, bm)

    def _determine_mult_color(self, bo, bm):
        """Determines the color all vertex colors should be multipled by in this span."""
        if self.geospan.props & plGeometrySpan.kDiffuseFoldedIn:
            color = bm.diffuse_color
            base_layer = self._find_bottom_of_stack()
            return (color.r, color.b, color.g, base_layer.opacity)
        if not bo.plasma_modifiers.lighting.preshade:
            return (0.0, 0.0, 0.0, 0.0)
        return (1.0, 1.0, 1.0, 1.0)

    def _find_bottom_of_stack(self) -> plLayerInterface:
        base_layer = self.geospan.material.object.layers[0].object
        while base_layer.underLay is not None:
            base_layer = base_layer.underLay.object
        return base_layer


class _RenderLevel:
    MAJOR_OPAQUE = 0
    MAJOR_FRAMEBUF = 1
    MAJOR_DEFAULT = 2
    MAJOR_BLEND = 4
    MAJOR_LATE = 8

    _MAJOR_SHIFT = 28
    _MINOR_MASK = ((1 << _MAJOR_SHIFT) - 1)

    def __init__(self, bo, pass_index, blend_span=False):
        if blend_span:
            self.level = self._determine_level(bo, blend_span)
        else:
            self.level = 0
        # Gulp... Hope you know what you're doing...
        self.minor += pass_index * 4

    def __eq__(self, other):
        return self.level == other.level

    def __hash__(self):
        return hash(self.level)

    def _get_major(self):
        return self.level >> self._MAJOR_SHIFT
    def _set_major(self, value):
        self.level = self._calc_level(value, self.minor)
    major = property(_get_major, _set_major)

    def _get_minor(self):
        return self.level & self._MINOR_MASK
    def _set_minor(self, value):
        self.level = self._calc_level(self.major, value)
    minor = property(_get_minor, _set_minor)

    def _calc_level(self, major : int, minor : int=0) -> int:
        return ((major << self._MAJOR_SHIFT) & 0xFFFFFFFF) | minor

    def _determine_level(self, bo : bpy.types.Object, blend_span : bool) -> int:
        mods = bo.plasma_modifiers
        if mods.test_property("draw_framebuf"):
            return self._calc_level(self.MAJOR_FRAMEBUF)
        elif mods.test_property("draw_opaque"):
            return self._calc_level(self.MAJOR_OPAQUE)
        elif mods.test_property("draw_no_defer"):
            blend_span = False

        blend_mod = mods.blend
        if blend_mod.enabled and blend_mod.has_dependencies:
            level = self._calc_level(self.MAJOR_FRAMEBUF)
            for i in blend_mod.iter_dependencies():
                level = max(level, self._determine_level(i, blend_span))
            return level + 4
        elif blend_span:
            return self._calc_level(self.MAJOR_BLEND)
        else:
            return self._calc_level(self.MAJOR_DEFAULT)


class _DrawableCriteria:
    def __init__(self, bo, geospan, pass_index):
        self.blend_span = bool(geospan.props & plGeometrySpan.kRequiresBlending)
        self.criteria = 0

        if self.blend_span:
            if self._face_sort_allowed(bo):
                self.criteria |= plDrawable.kCritSortFaces
            if self._span_sort_allowed(bo):
                self.criteria |= plDrawable.kCritSortSpans
        self.render_level = _RenderLevel(bo, pass_index, self.blend_span)

    def __eq__(self, other):
        if not isinstance(other, _DrawableCriteria):
            return False
        for i in ("blend_span", "render_level", "criteria"):
            if getattr(self, i) != getattr(other, i):
                return False
        return True

    def __hash__(self):
        return hash(self.render_level) ^ hash(self.blend_span) ^ hash(self.criteria)

    def _face_sort_allowed(self, bo):
        # For now, only test the modifiers
        # This will need to be tweaked further for GUIs...
        return not bo.plasma_modifiers.test_property("no_face_sort")

    def _span_sort_allowed(self, bo):
        # For now, only test the modifiers
        # This will need to be tweaked further for GUIs...
        return not bo.plasma_modifiers.test_property("no_face_sort")

    @property
    def span_type(self):
        if self.blend_span:
            return "BlendSpans"
        else:
            return "Spans"


class _GeoData:
    def __init__(self, numVtxs):
        self.blender2gs = [{} for i in range(numVtxs)]
        self.triangles = []
        self.vertices = []


class _MeshManager:
    def __init__(self, report=None):
        if report is not None:
            self._report = report
        self._overrides = {}

    @staticmethod
    def add_progress_presteps(report):
        report.progress_add_step("Applying Blender Mods")

    def _build_prop_dict(self, bstruct):
        props = {}
        for i in bstruct.bl_rna.properties:
            ident = i.identifier
            if ident == "rna_type":
                continue
            props[ident] = getattr(bstruct, ident) if getattr(i, "array_length", 0) == 0 else tuple(getattr(bstruct, ident))
        return props

    def __enter__(self):
        scene = bpy.context.scene
        self._report.progress_advance()
        self._report.progress_range = len(scene.objects)

        # Some modifiers like "Array" will procedurally generate new geometry that will impact
        # lightmap generation. The Blender Internal renderer does not seem to be smart enough to
        # take this into account. Thus, we temporarily apply modifiers to ALL meshes (even ones that
        # are not exported) such that we can generate proper lighting.
        mesh_type = bpy.types.Mesh
        for i in scene.objects:
            if isinstance(i.data, mesh_type) and i.is_modified(scene, "RENDER"):
                # Remember, storing actual pointers to the Blender objects can cause bad things to
                # happen because Blender's memory management SUCKS!
                self._overrides[i.name] = { "mesh": i.data.name, "modifiers": [] }
                i.data = i.to_mesh(scene, True, "RENDER", calc_tessface=False)

                # If the modifiers are left on the object, the lightmap bake can break under some
                # situations. Therefore, we now cache the modifiers and clear them away...
                if i.plasma_object.enabled:
                    cache_mods = self._overrides[i.name]["modifiers"]
                    for mod in i.modifiers:
                        cache_mods.append(self._build_prop_dict(mod))
                    i.modifiers.clear()
            self._report.progress_increment()
        return self

    def __exit__(self, type, value, traceback):
        data_bos, data_meshes = bpy.data.objects, bpy.data.meshes
        for obj_name, override in self._overrides.items():
            bo = data_bos.get(obj_name)

            # Reapply the old mesh
            trash_mesh, bo.data = bo.data, data_meshes.get(override["mesh"])
            data_meshes.remove(trash_mesh)

            # If modifiers were removed, reapply them now.
            for cached_mod in override["modifiers"]:
                mod = bo.modifiers.new(cached_mod["name"], cached_mod["type"])
                for key, value in cached_mod.items():
                    if key in {"name", "type"}:
                        continue
                    setattr(mod, key, value)


class MeshConverter(_MeshManager):
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self.material = material.MaterialConverter(exporter)

        self._dspans = {}
        self._mesh_geospans = {}

        # _report is a property on this subclass
        super().__init__()

    def _calc_num_uvchans(self, bo, mesh):
        max_user_texs = plGeometrySpan.kUVCountMask
        num_user_texs = len(mesh.tessface_uv_textures)
        total_texs = num_user_texs

        # Bump Mapping requires 2 magic channels
        if self.material.get_bump_layer(bo) is not None:
            total_texs += 2
            max_user_texs -= 2

        # Lightmapping requires its own LIGHTMAPGEN channel
        # NOTE: the LIGHTMAPGEN texture has already been created, so it is in num_user_texs
        lm = bo.plasma_modifiers.lightmap
        if lm.enabled and lm.bake_type == "lightmap":
            num_user_texs -= 1
            max_user_texs -= 1

        return (num_user_texs, total_texs, max_user_texs)

    def _check_vtx_alpha(self, mesh, material_idx):
        if material_idx is not None:
            polygons = (i for i in mesh.polygons if i.material_index == material_idx)
        else:
            polygons = mesh.polygons
        alpha_layer = self._find_vtx_alpha_layer(mesh.vertex_colors)
        if alpha_layer is None:
            return False
        alpha_loops = (alpha_layer[i.loop_start:i.loop_start+i.loop_total] for i in polygons)
        opaque = (sum(i.color) == len(i.color) for i in itertools.chain.from_iterable(alpha_loops))
        has_alpha = not all(opaque)
        return has_alpha

    def _check_vtx_nonpreshaded(self, bo, mesh, material_idx, base_layer):
        def check_layer_shading_animation(layer):
            if isinstance(layer, plLayerAnimationBase):
                return layer.opacityCtl is not None or layer.preshadeCtl is not None or layer.runtimeCtl is not None
            if layer.underLay is not None:
                return check_layer_shading_animation(layer.underLay.object)
            return False

        # TODO: if this is an avatar, we can't be non-preshaded.
        if check_layer_shading_animation(base_layer):
            return False
        if base_layer.state.shadeFlags & hsGMatState.kShadeEmissive:
            return False

        mods = bo.plasma_modifiers
        if mods.lighting.rt_lights:
            return True
        if mods.lightmap.bake_lightmap:
            return True
        if self._check_vtx_alpha(mesh, material_idx):
            return True

        return False

    def _create_geospan(self, bo, mesh, material_idx, bm, hsgmatKey):
        """Initializes a plGeometrySpan from a Blender Object and an hsGMaterial"""
        geospan = plGeometrySpan()
        geospan.material = hsgmatKey

        # GeometrySpan format
        # For now, we really only care about the number of UVW Channels
        user_uvws, total_uvws, max_user_uvws = self._calc_num_uvchans(bo, mesh)
        if total_uvws > plGeometrySpan.kUVCountMask:
            raise explosions.TooManyUVChannelsError(bo, bm, user_uvws, max_user_uvws)
        geospan.format = total_uvws

        def is_alpha_blended(layer):
            if layer.state.blendFlags & hsGMatState.kBlendMask:
                return True
            if layer.underLay is not None:
                return is_alpha_blended(layer.underLay.object)
            return False

        base_layer = hsgmatKey.object.layers[0].object
        if is_alpha_blended(base_layer) or self._check_vtx_alpha(mesh, material_idx):
            geospan.props |= plGeometrySpan.kRequiresBlending
        if self._check_vtx_nonpreshaded(bo, mesh, material_idx, base_layer):
            geospan.props |= plGeometrySpan.kLiteVtxNonPreshaded
        if (geospan.props & plGeometrySpan.kLiteMask) != plGeometrySpan.kLiteMaterial:
            geospan.props |= plGeometrySpan.kDiffuseFoldedIn

        mods = bo.plasma_modifiers
        if mods.lighting.rt_lights:
            geospan.props |= plGeometrySpan.kPropRunTimeLight
        if not bm.use_shadows:
            geospan.props |= plGeometrySpan.kPropNoShadow

        # Harvest lights
        permaLights, permaProjs = self._exporter().light.find_material_light_keys(bo, bm)
        for i in permaLights:
            geospan.addPermaLight(i)
        for i in permaProjs:
            geospan.addPermaProj(i)

        # If this object has a CI, we don't need xforms here...
        if self._exporter().has_coordiface(bo):
            geospan.localToWorld = hsMatrix44()
            geospan.worldToLocal = hsMatrix44()
        else:
            geospan.localToWorld = utils.matrix44(bo.matrix_basis)
            geospan.worldToLocal = geospan.localToWorld.inverse()
        return geospan

    def finalize(self):
        """Prepares all baked Plasma geometry to be flushed to the disk"""
        self._report.progress_advance()
        self._report.progress_range = len(self._dspans)
        inc_progress = self._report.progress_increment
        log_msg = self._report.msg

        log_msg("\nFinalizing Geometry")
        for loc in self._dspans.values():
            for dspan in loc.values():
                log_msg("[DrawableSpans '{}']", dspan.key.name, indent=1)

                # This mega-function does a lot:
                # 1. Converts SourceSpans (geospans) to Icicles and bakes geometry into plGBuffers
                # 2. Calculates the Icicle bounds
                # 3. Builds the plSpaceTree
                # 4. Clears the SourceSpans
                dspan.composeGeometry(True, True)
            inc_progress()

    def _export_geometry(self, bo, mesh, materials, geospans, mat2span_LUT):
        # Recall that materials is a mapping of exported materials to blender material indices.
        # Therefore, geodata maps blender material indices to working geometry data.
        # Maybe the logic is a bit inverted, but it keeps the inner loop simple.
        geodata = { idx: _GeoData(len(mesh.vertices)) for idx, _ in materials }
        bumpmap = self.material.get_bump_layer(bo)

        # Locate relevant vertex color layers now...
        lm = bo.plasma_modifiers.lightmap
        color = None if lm.bake_lightmap else self._find_vtx_color_layer(mesh.tessface_vertex_colors)
        alpha = self._find_vtx_alpha_layer(mesh.tessface_vertex_colors)

        # Convert Blender faces into things we can stuff into libHSPlasma
        for i, tessface in enumerate(mesh.tessfaces):
            data = geodata.get(tessface.material_index)
            if data is None:
                continue

            face_verts = []
            use_smooth = tessface.use_smooth
            dPosDu = hsVector3(0.0, 0.0, 0.0)
            dPosDv = hsVector3(0.0, 0.0, 0.0)

            # Unpack the UV coordinates from each UV Texture layer
            # NOTE: Blender has no third (W) coordinate
            tessface_uvws = [uvtex.data[i].uv for uvtex in mesh.tessface_uv_textures]

            # Unpack colors
            if color is None:
                tessface_colors = ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0))
            else:
                src = color[i]
                tessface_colors = (src.color1, src.color2, src.color3, src.color4)

            # Unpack alpha values
            if alpha is None:
                tessface_alphas = (1.0, 1.0, 1.0, 1.0)
            else:
                src = alpha[i]
                # average color becomes the alpha value
                tessface_alphas = ((sum(src.color1) / 3), (sum(src.color2) / 3),
                                   (sum(src.color3) / 3), (sum(src.color4) / 3))

            if bumpmap is not None:
                gradPass = []
                gradUVWs = []

                if len(tessface.vertices) != 3:
                    gradPass.append([tessface.vertices[0], tessface.vertices[1], tessface.vertices[2]])
                    gradPass.append([tessface.vertices[0], tessface.vertices[2], tessface.vertices[3]])
                    gradUVWs.append((tuple((uvw[0] for uvw in tessface_uvws)),
                                     tuple((uvw[1] for uvw in tessface_uvws)),
                                     tuple((uvw[2] for uvw in tessface_uvws))))
                    gradUVWs.append((tuple((uvw[0] for uvw in tessface_uvws)),
                                     tuple((uvw[2] for uvw in tessface_uvws)),
                                     tuple((uvw[3] for uvw in tessface_uvws))))
                else:
                    gradPass.append(tessface.vertices)
                    gradUVWs.append((tuple((uvw[0] for uvw in tessface_uvws)),
                                     tuple((uvw[1] for uvw in tessface_uvws)),
                                     tuple((uvw[2] for uvw in tessface_uvws))))

                for p, vids in enumerate(gradPass):
                    dPosDu += self._get_bump_gradient(bumpmap[1], gradUVWs[p], mesh, vids, bumpmap[0], 0)
                    dPosDv += self._get_bump_gradient(bumpmap[1], gradUVWs[p], mesh, vids, bumpmap[0], 1)
                dPosDv = -dPosDv

            # Convert to per-material indices
            for j, vertex in enumerate(tessface.vertices):
                uvws = tuple([uvw[j] for uvw in tessface_uvws])

                # Calculate vertex colors.
                if mat2span_LUT:
                    mult_color = geospans[mat2span_LUT[tessface.material_index]].mult_color
                else:
                    mult_color = (1.0, 1.0, 1.0, 1.0)
                tessface_color, tessface_alpha = tessface_colors[j], tessface_alphas[j]
                vertex_color = (int(tessface_color[0] * mult_color[0] * 255),
                                int(tessface_color[1] * mult_color[1] * 255),
                                int(tessface_color[2] * mult_color[2] * 255),
                                int(tessface_alpha    * mult_color[0] * 255))

                # Now, we'll index into the vertex dict using the per-face elements :(
                # We're using tuples because lists are not hashable. The many mathutils and PyHSPlasma
                # types are not either, and it's entirely too much work to fool with all that.
                coluv = (vertex_color, uvws)
                if coluv not in data.blender2gs[vertex]:
                    source = mesh.vertices[vertex]
                    geoVertex = plGeometrySpan.TempVertex()
                    geoVertex.position = hsVector3(*source.co)

                    # If this face has smoothing, use the vertex normal
                    # Otherwise, use the face normal
                    normal = source.normal if use_smooth else tessface.normal

                    # MOUL/DX9 craps its pants if any element of the normal is exactly 0.0
                    normal = map(lambda x: max(x, 0.01) if x >= 0.0 else min(x, -0.01), normal)
                    normal = hsVector3(*normal)
                    normal.normalize()
                    geoVertex.normal = normal

                    geoVertex.color = hsColor32(*vertex_color)
                    uvs = [hsVector3(uv[0], 1.0 - uv[1], 0.0) for uv in uvws]
                    if bumpmap is not None:
                        uvs.append(dPosDu)
                        uvs.append(dPosDv)
                    geoVertex.uvs = uvs

                    idx = len(data.vertices)
                    data.blender2gs[vertex][coluv] = idx
                    data.vertices.append(geoVertex)
                    face_verts.append(idx)
                else:
                    # If we have a bump mapping layer, then we need to add the bump gradients for
                    # this face to the vertex's magic channels
                    if bumpmap is not None:
                        num_user_uvs = len(uvws)
                        geoVertex = data.vertices[data.blender2gs[vertex][coluv]]

                        # Unfortunately, PyHSPlasma returns a copy of everything. Previously, editing
                        # in place would result in silent failures; however, as of python_refactor,
                        # PyHSPlasma now returns tuples to indicate this.
                        geoUVs = list(geoVertex.uvs)
                        geoUVs[num_user_uvs] += dPosDu
                        geoUVs[num_user_uvs+1] += dPosDv
                        geoVertex.uvs = geoUVs
                    face_verts.append(data.blender2gs[vertex][coluv])

            # Convert to triangles, if need be...
            if len(face_verts) == 3:
                data.triangles += face_verts
            elif len(face_verts) == 4:
                data.triangles += (face_verts[0], face_verts[1], face_verts[2])
                data.triangles += (face_verts[0], face_verts[2], face_verts[3])

        # Time to finish it up...
        for i, data in enumerate(geodata.values()):
            geospan = geospans[i].geospan
            numVerts = len(data.vertices)
            numUVs = geospan.format & plGeometrySpan.kUVCountMask

            # There is a soft limit of 0x8000 vertices per span in Plasma, but the limit is
            # theoretically 0xFFFF because this field is a 16-bit integer. However, bad things
            # happen in MOUL when we have over 0x8000 vertices. I've also received tons of reports
            # of stack dumps in PotS when modifiers are applied, so we're going to limit to 0x8000.
            #     TODO: consider busting up the mesh into multiple geospans?
            #           or hack plDrawableSpans::composeGeometry to do it for us?
            if numVerts > _WARN_VERTS_PER_SPAN:
                raise explosions.TooManyVerticesError(bo.data.name, geospan.material.name, numVerts)

            # If we're bump mapping, we need to normalize our magic UVW channels
            if bumpmap is not None:
                for vtx in data.vertices:
                    uvMap = vtx.uvs
                    uvMap[numUVs - 2].normalize()
                    uvMap[numUVs - 1].normalize()
                    vtx.uvs = uvMap

            # If we're still here, let's add our data to the GeometrySpan
            geospan.indices = data.triangles
            geospan.vertices = data.vertices


    def _get_bump_gradient(self, xform, uvws, mesh, vIds, uvIdx, iUV):
        v0 = hsVector3(*mesh.vertices[vIds[0]].co)
        v1 = hsVector3(*mesh.vertices[vIds[1]].co)
        v2 = hsVector3(*mesh.vertices[vIds[2]].co)

        uv0 = (uvws[0][uvIdx][0], uvws[0][uvIdx][1], 0.0)
        uv1 = (uvws[1][uvIdx][0], uvws[1][uvIdx][1], 0.0)
        uv2 = (uvws[2][uvIdx][0], uvws[2][uvIdx][1], 0.0)

        notUV = int(not iUV)
        _REAL_SMALL = 0.000001

        delta = uv0[notUV] - uv1[notUV]
        if fabs(delta) < _REAL_SMALL:
            return v1 - v0 if uv0[iUV] - uv1[iUV] < 0 else v0 - v1

        delta = uv2[notUV] - uv1[notUV]
        if fabs(delta) < _REAL_SMALL:
            return v1 - v2 if uv2[iUV] - uv1[iUV] < 0 else v2 - v1

        delta = uv2[notUV] - uv0[notUV]
        if fabs(delta) < _REAL_SMALL:
            return v0 - v2 if uv2[iUV] - uv0[iUV] < 0 else v2 - v0

        # On to the real fun...
        delta = uv0[notUV] - uv1[notUV]
        delta = 1.0 / delta
        v0Mv1 = v0 - v1
        v0Mv1 *= delta
        v0uv = (uv0[iUV] - uv1[iUV]) * delta

        delta = uv2[notUV] - uv1[notUV]
        delta = 1.0 / delta
        v2Mv1 = v2 - v1
        v2Mv1 *= delta
        v2uv = (uv2[iUV] - uv1[iUV]) * delta

        return v0Mv1 - v2Mv1 if v0uv > v2uv else v2Mv1 - v0Mv1

    def _enumerate_materials(self, bo, mesh):
        material_source = mesh.materials
        valid_materials = set((tf.material_index for tf in mesh.tessfaces if material_source[tf.material_index] is not None))
        # Sequence of tuples (material_index, material)
        return sorted(((i, material_source[i]) for i in valid_materials), key=lambda x: x[0])

    def export_object(self, bo):
        # If this object has modifiers, then it's a unique mesh, and we don't need to try caching it
        # Otherwise, let's *try* to share meshes as best we can...
        if bo.modifiers:
            drawables = self._export_mesh(bo)
        else:
            drawables = self._mesh_geospans.get(bo.data, None)
            if drawables is None:
                drawables = self._export_mesh(bo)

        # Create the DrawInterface
        if drawables:
            diface = self._mgr.find_create_object(plDrawInterface, bl=bo)
            for dspan_key, idx in drawables:
                diface.addDrawable(dspan_key, idx)

    def _export_mesh(self, bo):
        # Previously, this called bo.to_mesh to apply modifiers. However, due to limitations in the
        # lightmap generation, this is now done for all modified mesh objects before any Plasma data
        # is exported.
        mesh = bo.data
        mesh.calc_tessface()

        # Step 0.8: Determine materials needed for export... Three considerations here:
        #           1) Some materials can be None, so that's junk.
        #           2) Some materials are present but have no valid geometry (D'oh)
        #           3) TODO: Materials may be attached to the object, not the mesh.
        materials = self._enumerate_materials(bo, mesh)
        if not materials:
            return None

        # Step 1: Export all of the doggone materials.
        geospans, mat2span_LUT = self._export_material_spans(bo, mesh, materials)

        # Step 2: Export Blender mesh data to Plasma GeometrySpans
        self._export_geometry(bo, mesh, materials, geospans, mat2span_LUT)

        # Step 3: Add plGeometrySpans to the appropriate DSpan and create indices
        _diindices = {}
        for i in geospans:
            dspan = self._find_create_dspan(bo, i.geospan, i.pass_index)
            self._report.msg("Exported hsGMaterial '{}' geometry into '{}'",
                             i.geospan.material.name, dspan.key.name, indent=1)
            idx = dspan.addSourceSpan(i.geospan)
            diidx = _diindices.setdefault(dspan, [])
            diidx.append(idx)

        # Step 3.1: Harvest Span indices and create the DIIndices
        drawables = []
        for dspan, indices in _diindices.items():
            dii = plDISpanIndex()
            dii.indices = indices
            idx = dspan.addDIIndex(dii)
            drawables.append((dspan.key, idx))
        return drawables

    def _export_material_spans(self, bo, mesh, materials):
        """Exports all Materials and creates plGeometrySpans"""
        waveset_mod = bo.plasma_modifiers.water_basic
        if waveset_mod.enabled:
            if len(materials) > 1:
                msg = "'{}' is a WaveSet -- only one material is supported".format(bo.name)
                self._exporter().report.warn(msg, indent=1)
            blmat = materials[0][1]
            matKey = self.material.export_waveset_material(bo, blmat)
            geospan = self._create_geospan(bo, mesh, None, blmat, matKey)

            # FIXME: Can some of this be generalized?
            geospan.props |= (plGeometrySpan.kWaterHeight | plGeometrySpan.kLiteVtxNonPreshaded |
                              plGeometrySpan.kPropReverseSort | plGeometrySpan.kPropNoShadow)
            geospan.waterHeight = bo.location[2]
            return [_GeoSpan(bo, blmat, geospan)], None
        else:
            geospans = [None] * len(materials)
            mat2span_LUT = {}
            for i, (blmat_idx, blmat) in enumerate(materials):
                matKey = self.material.export_material(bo, blmat)
                geospans[i] = _GeoSpan(bo, blmat,
                                       self._create_geospan(bo, mesh, blmat_idx, blmat, matKey),
                                       blmat.pass_index)
                mat2span_LUT[blmat_idx] = i
            return geospans, mat2span_LUT

    def _find_create_dspan(self, bo, geospan, pass_index):
        location = self._mgr.get_location(bo)
        if location not in self._dspans:
            self._dspans[location] = {}

        # This is where we figure out which DSpan this goes into. To vaguely summarize the rules...
        # BlendSpans: anything with an alpha blended layer
        # SortSpans: means we should sort the spans in this DSpan with all other span in this pass
        # SortFaces: means we should sort the faces in this span only
        # We're using pass index to do just what it was designed for. Cyan has a nicer "depends on"
        # draw component, but pass index is the Blender way, so that's what we're doing.
        crit = _DrawableCriteria(bo, geospan, pass_index)

        if crit not in self._dspans[location]:
            # AgeName_[District_]_Page_RenderLevel_Crit[Blend]Spans
            # Just because it's nice to be consistent
            node = self._mgr.get_scene_node(location=location)
            name = "{}_{:08X}_{:X}{}".format(node.name, crit.render_level.level, crit.criteria, crit.span_type)
            dspan = self._mgr.add_object(pl=plDrawableSpans, name=name, loc=location)

            criteria = crit.criteria
            dspan.criteria = criteria
            if criteria & plDrawable.kCritSortFaces:
                dspan.props |= plDrawable.kPropSortFaces
            if criteria & plDrawable.kCritSortSpans:
                dspan.props |= plDrawable.kPropSortSpans
            dspan.renderLevel = crit.render_level.level
            dspan.sceneNode = node # AddViaNotify

            self._dspans[location][crit] = dspan
            return dspan
        else:
            return self._dspans[location][crit]

    def _find_vtx_alpha_layer(self, color_collection):
        alpha_layer = next((i for i in color_collection if i.name.lower() == "alpha"), None)
        if alpha_layer is not None:
            return alpha_layer.data
        return None

    def _find_vtx_color_layer(self, color_collection):
        manual_layer = next((i for i in color_collection if i.name.lower() in _VERTEX_COLOR_LAYERS), None)
        if manual_layer is not None:
            return manual_layer.data
        baked_layer = color_collection.get("autocolor")
        if baked_layer is not None:
            return baked_layer.data
        return None

    @property
    def _mgr(self):
        return self._exporter().mgr

    @property
    def _report(self):
        return self._exporter().report
