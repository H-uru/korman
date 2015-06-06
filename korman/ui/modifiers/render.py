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

def lightmap(modifier, layout, context):
    col = layout.column(align=True)
    col.row(align=True).prop(modifier, "quality", expand=True)
    col.operator("object.plasma_lightmap_preview", "Preview Lightmap", icon="RENDER_STILL")

    # Kind of clever stuff to show the user a preview...
    # We can't show images, so we make a hidden ImageTexture called LIGHTMAPGEN_PREVIEW. We check
    # the backing image name to see if it's for this lightmap. If so, you have a preview. If not,
    # well... It was nice knowing you!
    tex = bpy.data.textures.get("LIGHTMAPGEN_PREVIEW")
    if tex is not None:
        im_name = "{}_LIGHTMAPGEN".format(context.active_object.name)
        if tex.image.name == im_name:
            layout.template_preview(tex, show_buttons=False)
