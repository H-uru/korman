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

from PyHSPlasma import *

def matrix44(blmat):
    """Converts a mathutils.Matrix to an hsMatrix44"""
    hsmat = hsMatrix44()
    for i in range(4):
        hsmat[0, i] = blmat[i][0]
        hsmat[1, i] = blmat[i][1]
        hsmat[2, i] = blmat[i][2]
        hsmat[3, i] = blmat[i][3]
    return hsmat

def vector3(blvec):
    """Converts a mathutils.Vector to an hsVector3"""
    return hsVector3(blvec.x, blvec.y, blvec.z)
