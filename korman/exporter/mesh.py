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
from . import material
from . import utils

_MAX_VERTS_PER_SPAN = 0xFFFF
_WARN_VERTS_PER_SPAN = 0x8000

class _RenderLevel:
    MAJOR_OPAQUE = 0
    MAJOR_FRAMEBUF = 1
    MAJOR_DEFAULT = 2
    MAJOR_BLEND = 4
    MAJOR_LATE = 8

    _MAJOR_SHIFT = 28
    _MINOR_MASK = ((1 << _MAJOR_SHIFT) - 1)

    def __init__(self, hsgmat, pass_index):
        # TODO: Use hsGMaterial to determine major and minor
        self.level = 0

        # We use the blender material's pass index (which we stashed in the hsGMaterial) to increment
        # the render pass, just like it says...
        self.level += pass_index

    def __hash__(self):
        return hash(self.level)

    def _get_major(self):
        return self.level >> _MAJOR_SHIFT
    def _set_major(self, value):
        self.level = ((value << _MAJOR_SHIFT) & 0xFFFFFFFF) | self.minor
    major = property(_get_major, _set_major)

    def _get_minor(self):
        return self.level & _MINOR_MASK
    def _set_minor(self, value):
        self.level = ((self.major << _MAJOR_SHIFT) & 0xFFFFFFFF) | value
    minor = property(_get_minor, _set_minor)


class _DrawableCriteria:
    def __init__(self, hsgmat, pass_index):
        _layer = hsgmat.layers[0].object # better doggone well have a layer...
        self.blend_span = bool(_layer.state.blendFlags & hsGMatState.kBlendMask)
        self.criteria = 0 # TODO
        self.render_level = _RenderLevel(hsgmat, pass_index)

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


class MeshConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self.material = material.MaterialConverter(exporter)

        self._dspans = {}
        self._mesh_geospans = {}

    def _create_geospan(self, bo, mesh, bm, hsgmat):
        """Initializes a plGeometrySpan from a Blender Object and an hsGMaterial"""
        geospan = plGeometrySpan()
        geospan.material = hsgmat

        # GeometrySpan format
        # For now, we really only care about the number of UVW Channels
        numUVWchans = len(mesh.tessface_uv_textures)
        if numUVWchans > plGeometrySpan.kUVCountMask:
            raise explosions.TooManyUVChannelsError(bo, bm)
        geospan.format = numUVWchans

        # TODO: Props
        # TODO: RunTime lights (requires libHSPlasma feature)

        # If this object has a CI, we don't need xforms here...
        if self._mgr.find_key(bo, plCoordinateInterface) is not None:
            geospan.localToWorld = hsMatrix44()
            geospan.worldToLocal = hsMatrix44()
        else:
            geospan.worldToLocal = utils.matrix44(bo.matrix_basis)
            geospan.localToWorld = geospan.worldToLocal.inverse()
        return geospan

    def finalize(self):
        """Prepares all baked Plasma geometry to be flushed to the disk"""
        print("\n=== Finalizing Geometry ===")

        for loc in self._dspans.values():
            for dspan in loc.values():
                print("    Finalizing DSpan: '{}'".format(dspan.key.name))
    
                # This mega-function does a lot:
                # 1. Converts SourceSpans (geospans) to Icicles and bakes geometry into plGBuffers
                # 2. Calculates the Icicle bounds
                # 3. Builds the plSpaceTree
                # 4. Clears the SourceSpans
                dspan.composeGeometry(True, True)

    def _export_geometry(self, mesh, geospans):
        _geodatacls = type("_GeoData",
                       (object,),
                       {
                           "blender2gs": [{} for i in mesh.vertices],
                           "triangles": [],
                           "vertices": []
                       })
        geodata = [_geodatacls() for i in mesh.materials]

        # Convert Blender faces into things we can stuff into libHSPlasma
        for i, tessface in enumerate(mesh.tessfaces):
            data = geodata[tessface.material_index]
            face_verts = []

            # Convert to per-material indices
            for j in tessface.vertices:
                # Unpack the UV coordinates from each UV Texture layer
                uvws = []
                for uvtex in mesh.tessface_uv_textures:
                    uv = getattr(uvtex.data[i], "uv{}".format(j+1))
                    # In Blender, UVs have no Z coordinate
                    uvws.append((uv.x, uv.y))

                # Grab VCols (TODO--defaulting to white for now)
                # This will be finalized once the vertex color light code baking is in
                color = (255, 255, 255, 255)

                # Now, we'll index into the vertex dict using the per-face elements :(
                # We're using tuples because lists are not hashable. The many mathutils and PyHSPlasma
                # types are not either, and it's entirely too much work to fool with all that.
                coluv = (color, tuple(uvws))
                if coluv not in data.blender2gs[j]:
                    source = mesh.vertices[j]
                    vertex = plGeometrySpan.TempVertex()
                    vertex.position = utils.vector3(source.co)
                    vertex.normal = utils.vector3(source.normal)
                    vertex.color = hsColor32(*color)
                    vertex.uvs = [hsVector3(uv[0], 1.0-uv[1], 0.0) for uv in uvws]
                    data.blender2gs[j][coluv] = len(data.vertices)
                    data.vertices.append(vertex)
                face_verts.append(data.blender2gs[j][coluv])

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
        # Have we already exported this mesh?
        try:
            drawables = self._mesh_geospans[bo.data]
        except LookupError:
            drawables = self._export_mesh(bo)

        # Create the DrawInterface
        diface = self._mgr.add_object(pl=plDrawInterface, bl=bo)
        for dspan_key, idx in drawables:
            diface.addDrawable(dspan_key, idx)
        return diface.key

    def _export_mesh(self, bo):
        # First, we need to grab the object's mesh...
        mesh = bo.data
        mesh.update(calc_tessface=True)

        # Step 1: Export all of the doggone materials.
        geospans = self._export_material_spans(bo, mesh)

        # Step 2: Export Blender mesh data to Plasma GeometrySpans
        self._export_geometry(mesh, geospans)

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
            hsgmat = self.material.export_material(bo, blmat)
            geospans[i] = (self._create_geospan(bo, mesh, blmat, hsgmat), blmat.pass_index)
        return geospans

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
            node = self._mgr.get_scene_node(location)
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
