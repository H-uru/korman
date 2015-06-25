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
from PyHSPlasma import *
import weakref

from . import explosions
from .. import helpers
from . import material
from . import utils

_MAX_VERTS_PER_SPAN = 0xFFFF
_WARN_VERTS_PER_SPAN = 0x8000

_VERTEX_COLOR_LAYERS = {"col", "color", "colour"}

class _RenderLevel:
    MAJOR_OPAQUE = 0
    MAJOR_FRAMEBUF = 1
    MAJOR_DEFAULT = 2
    MAJOR_BLEND = 4
    MAJOR_LATE = 8

    _MAJOR_SHIFT = 28
    _MINOR_MASK = ((1 << _MAJOR_SHIFT) - 1)

    def __init__(self, hsgmat, pass_index, blendSpan=False):
        self.level = 0

        # Naive... BlendSpans (any blending on the first layer) are MAJOR_BLEND
        if blendSpan:
            self.major = self.MAJOR_DEFAULT

        # We use the blender material's pass index (which we stashed in the hsGMaterial) to increment
        # the render pass, just like it says...
        self.level += pass_index

    def __eq__(self, other):
        return self.level == other.level

    def __hash__(self):
        return hash(self.level)

    def _get_major(self):
        return self.level >> self._MAJOR_SHIFT
    def _set_major(self, value):
        self.level = ((value << self._MAJOR_SHIFT) & 0xFFFFFFFF) | self.minor
    major = property(_get_major, _set_major)

    def _get_minor(self):
        return self.level & self._MINOR_MASK
    def _set_minor(self, value):
        self.level = ((self.major << self._MAJOR_SHIFT) & 0xFFFFFFFF) | value
    minor = property(_get_minor, _set_minor)


class _DrawableCriteria:
    def __init__(self, hsgmat, pass_index):
        for layer in hsgmat.layers:
            if layer.object.state.blendFlags & hsGMatState.kBlendMask:
                self.blend_span = True
                break
        else:
            self.blend_span = False
        self.criteria = 0 # TODO
        self.render_level = _RenderLevel(hsgmat, pass_index, self.blend_span)

    def __eq__(self, other):
        if not isinstance(other, _DrawableCriteria):
            return False
        for i in ("blend_span", "render_level", "criteria"):
            if getattr(self, i) != getattr(other, i):
                return False
        return True

    def __hash__(self):
        return hash(self.render_level) ^ hash(self.blend_span) ^ hash(self.criteria)

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


class MeshConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self.material = material.MaterialConverter(exporter)

        self._dspans = {}
        self._mesh_geospans = {}

    def _create_geospan(self, bo, mesh, bm, hsgmatKey):
        """Initializes a plGeometrySpan from a Blender Object and an hsGMaterial"""
        geospan = plGeometrySpan()
        geospan.material = hsgmatKey

        # GeometrySpan format
        # For now, we really only care about the number of UVW Channels
        numUVWchans = len(mesh.tessface_uv_textures)
        if numUVWchans > plGeometrySpan.kUVCountMask:
            raise explosions.TooManyUVChannelsError(bo, bm)
        geospan.format = numUVWchans

        # Harvest lights
        permaLights, permaProjs = self._exporter().light.find_material_light_keys(bo, bm)
        for i in permaLights:
            geospan.addPermaLight(i)
        for i in permaProjs:
            geospan.addPermaProjs(i)

        # If this object has a CI, we don't need xforms here...
        if self._mgr.has_coordiface(bo):
            geospan.localToWorld = hsMatrix44()
            geospan.worldToLocal = hsMatrix44()
        else:
            geospan.localToWorld = utils.matrix44(bo.matrix_basis)
            geospan.worldToLocal = geospan.localToWorld.inverse()
        return geospan

    def finalize(self):
        """Prepares all baked Plasma geometry to be flushed to the disk"""

        for loc in self._dspans.values():
            for dspan in loc.values():
                print("\n[DrawableSpans '{}']".format(dspan.key.name))
                print("    Composing geometry data")

                # This mega-function does a lot:
                # 1. Converts SourceSpans (geospans) to Icicles and bakes geometry into plGBuffers
                # 2. Calculates the Icicle bounds
                # 3. Builds the plSpaceTree
                # 4. Clears the SourceSpans
                dspan.composeGeometry(True, True)

                # Might as well say something else just to fascinate anyone who is playing along
                # at home (and actually enjoys reading these lawgs)
                print("    Bounds and SpaceTree in the saddle")

    def _export_geometry(self, bo, mesh, geospans):
        geodata = [_GeoData(len(mesh.vertices)) for i in mesh.materials]

        # Locate relevant vertex color layers now...
        color, alpha = None, None
        for vcol_layer in mesh.tessface_vertex_colors:
            name = vcol_layer.name.lower()
            if name in _VERTEX_COLOR_LAYERS:
                color = vcol_layer.data
            elif name == "autocolor" and color is None and not bo.plasma_modifiers.lightmap.enabled:
                color = vcol_layer.data
            elif name == "alpha":
                alpha = vcol_layer.data

        # Convert Blender faces into things we can stuff into libHSPlasma
        for i, tessface in enumerate(mesh.tessfaces):
            data = geodata[tessface.material_index]
            face_verts = []

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
                tessface_alphas = (((src.color1[0] + src.color1[1] + src.color1[2]) / 3),
                                   ((src.color2[0] + src.color2[1] + src.color2[2]) / 3),
                                   ((src.color3[0] + src.color3[1] + src.color3[2]) / 3),
                                   ((src.color4[0] + src.color4[1] + src.color4[2]) / 3))

            # Convert to per-material indices
            for j, vertex in enumerate(tessface.vertices):
                uvws = tuple([uvw[j] for uvw in tessface_uvws])

                # Grab VCols
                vertex_color = (int(tessface_colors[j][0] * 255), int(tessface_colors[j][1] * 255),
                                int(tessface_colors[j][2] * 255), int(tessface_alphas[j] * 255))

                # Now, we'll index into the vertex dict using the per-face elements :(
                # We're using tuples because lists are not hashable. The many mathutils and PyHSPlasma
                # types are not either, and it's entirely too much work to fool with all that.
                coluv = (vertex_color, uvws)
                if coluv not in data.blender2gs[vertex]:
                    source = mesh.vertices[vertex]
                    geoVertex = plGeometrySpan.TempVertex()
                    geoVertex.position = utils.vector3(source.co)
                    geoVertex.normal = utils.vector3(source.normal)
                    geoVertex.color = hsColor32(*vertex_color)
                    geoVertex.uvs = [hsVector3(uv[0], uv[1], 0.0) for uv in uvws]
                    data.blender2gs[vertex][coluv] = len(data.vertices)
                    data.vertices.append(geoVertex)
                face_verts.append(data.blender2gs[vertex][coluv])

            # Convert to triangles, if need be...
            if len(face_verts) == 3:
                data.triangles += face_verts
            elif len(face_verts) == 4:
                data.triangles += (face_verts[0], face_verts[1], face_verts[2])
                data.triangles += (face_verts[0], face_verts[2], face_verts[3])

        # Time to finish it up...
        for i, data in enumerate(geodata):
            geospan = geospans[i][0]
            numVerts = len(data.vertices)

            # Soft vertex limit at 0x8000 for PotS and below. Works fine as long as it's a uint16
            # MOUL only allows signed int16s, however :/
            if numVerts > _MAX_VERTS_PER_SPAN or (numVerts > _WARN_VERTS_PER_SPAN and self._mgr.getVer() >= pvMoul):
                raise explosions.TooManyVerticesError(mesh.name, geospan.material.name, numVerts)
            elif numVerts > _WARN_VERTS_PER_SPAN:
                pass # FIXME

            # If we're still here, let's add our data to the GeometrySpan
            geospan.indices = data.triangles
            geospan.vertices = data.vertices

    def export_object(self, bo):
        # If this object has modifiers, then it's a unique mesh, and we don't need to try caching it
        # Otherwise, let's *try* to share meshes as best we can...
        if not bo.modifiers:
            drawables = self._mesh_geospans.get(bo.data, None)
            if drawables is None:
                drawables = self._export_mesh(bo)

        # Create the DrawInterface
        diface = self._mgr.add_object(pl=plDrawInterface, bl=bo)
        for dspan_key, idx in drawables:
            diface.addDrawable(dspan_key, idx)

    def _export_mesh(self, bo):
        # Step 0.8: If this mesh wants to be lit, we need to go ahead and generate it.
        self._export_static_lighting(bo)

        # Step 0.9: Update the mesh such that we can do things and schtuff...
        mesh = bo.to_mesh(bpy.context.scene, True, "RENDER", calc_tessface=True)
        with helpers.TemporaryObject(mesh, bpy.data.meshes.remove):
            # Step 1: Export all of the doggone materials.
            geospans = self._export_material_spans(bo, mesh)

            # Step 2: Export Blender mesh data to Plasma GeometrySpans
            self._export_geometry(bo, mesh, geospans)

            # Step 3: Add plGeometrySpans to the appropriate DSpan and create indices
            _diindices = {}
            for geospan, pass_index in geospans:
                dspan = self._find_create_dspan(bo, geospan.material.object, pass_index)
                print("    Exported hsGMaterial '{}' geometry into '{}'".format(geospan.material.name, dspan.key.name))
                idx = dspan.addSourceSpan(geospan)
                if dspan not in _diindices:
                    _diindices[dspan] = [idx,]
                else:
                    _diindices[dspan].append(idx)

            # Step 3.1: Harvest Span indices and create the DIIndices
            drawables = []
            for dspan, indices in _diindices.items():
                dii = plDISpanIndex()
                dii.indices = indices
                idx = dspan.addDIIndex(dii)
                drawables.append((dspan.key, idx))
            return drawables

    def _export_material_spans(self, bo, mesh):
        """Exports all Materials and creates plGeometrySpans"""
        geospans = [None] * len(mesh.materials)
        for i, blmat in enumerate(mesh.materials):
            matKey = self.material.export_material(bo, blmat)
            geospans[i] = (self._create_geospan(bo, mesh, blmat, matKey), blmat.pass_index)
        return geospans

    def _export_static_lighting(self, bo):
        helpers.make_active_selection(bo)
        lm = bo.plasma_modifiers.lightmap
        if lm.enabled:
            print("    Baking lightmap...")
            bpy.ops.object.plasma_lightmap_autobake(light_group=lm.light_group)
        else:
            for vcol_layer in bo.data.vertex_colors:
                name = vcol_layer.name.lower()
                if name in _VERTEX_COLOR_LAYERS:
                    break
            else:
                print("    Baking crappy vertex color lighting...")
                bpy.ops.object.plasma_vertexlight_autobake()


    def _find_create_dspan(self, bo, hsgmat, pass_index):
        location = self._mgr.get_location(bo)
        if location not in self._dspans:
            self._dspans[location] = {}

        # This is where we figure out which DSpan this goes into. To vaguely summarize the rules...
        # BlendSpans: anything with an alpha blended layer
        # [... document me ...]
        # We're using pass index to do just what it was designed for. Cyan has a nicer "depends on"
        # draw component, but pass index is the Blender way, so that's what we're doing.
        crit = _DrawableCriteria(hsgmat, pass_index)

        if crit not in self._dspans[location]:
            # AgeName_[District_]_Page_RenderLevel_Crit[Blend]Spans
            # Just because it's nice to be consistent
            node = self._mgr.get_scene_node(location=location)
            name = "{}_{:08X}_{:X}{}".format(node.name, crit.render_level.level, crit.criteria, crit.span_type)
            dspan = self._mgr.add_object(pl=plDrawableSpans, name=name, loc=location)

            dspan.criteria = crit.criteria
            # TODO: props
            dspan.renderLevel = crit.render_level.level
            dspan.sceneNode = node # AddViaNotify

            self._dspans[location][crit] = dspan
            return dspan
        else:
            return self._dspans[location][crit]

    @property
    def _mgr(self):
        return self._exporter().mgr
