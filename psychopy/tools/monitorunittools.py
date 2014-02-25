#!/usr/bin/env python2

# Part of the PsychoPy library
# Copyright (C) 2014 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

'''Functions and classes related to unit conversion respective to a particular
monitor'''

from psychopy import monitors
import numpy as np
from np import sin, cos, tan, pi, radians, degrees, hypot

# Maps supported coordinate unit type names to the function that converts
# the given unit type to PsychoPy OpenGL pix unit space.
_unit2PixMappings = dict()

#the following are to be used by convertToPix
def _pix2pix(vertices, pos, win = None):
    return pos+vertices
_unit2PixMappings['pix'] = _pix2pix

def _cm2pix(vertices, pos, win):
    return cm2pix(pos+vertices, win.monitor)
_unit2PixMappings['cm'] = _cm2pix

def _deg2pix(vertices, pos, win):
    return deg2pix(pos+vertices, win.monitor)
_unit2PixMappings['deg'] = _deg2pix

def _degFlatPos2pix(vertices, pos, win):
    posCorrected = deg2pix(pos, win.monitor, correctFlat=True)
    vertices = deg2pix(vertices, win.monitor, correctFlat=False)
    return posCorrected+vertices
_unit2PixMappings['degFlatPos'] = _degFlatPos2pix

def _degFlat2pix(vertices, pos, win):
    return deg2pix(pos+vertices, win.monitor, correctFlat=True)
_unit2PixMappings['degFlat'] = _degFlat2pix

def _norm2pix(vertices, pos, win):
    return (pos+vertices) * win.size/2.0
_unit2PixMappings['norm'] = _norm2pix

def _height2pix(vertices, pos, win):
    return (pos+vertices) * win.size[1]
_unit2PixMappings['height'] = _height2pix

def convertToPix(vertices, pos, units, win):
    """Takes vertices and position, combines and converts to pixels from any unit

    The reason that `pos` and `vertices` are provided separately is that it allows
    the conversion from deg to apply flat-screen correction to each separately.

    The reason that these use function args rather than relying on self.pos
    is that some stimuli (e.g. ElementArrayStim use other terms like fieldPos)
    """
    unit2pix_func = _unit2PixMappings.get(units)
    if unit2pix_func:
        return unit2pix_func(vertices, pos, win)
    else:
        raise ValueError("The unit type [{0}] is not registered with PsychoPy".format(units))

def addUnitTypeConversion(unit_label, mapping_func):
    """
    Add support for converting units specified by unit_label to pixels to be
    used by convertToPix (therefore a valid unit for your PsychoPy stimuli)

    mapping_func must have the function prototype:

    def mapping_func(vertices, pos, win):
        # Convert the input vertices, pos to pixel positions PsychoPy will use
        # for OpenGL call.

        # unit type -> pixel mapping logic here
        # .....

        return pix
    """
    if unit_label in unit2PixMappings:
        raise ValueError("The unit type label [{0}] is already registered with PsychoPy".format(unit_label))
    unit2PixMappings[unit_label]=mapping_func

#
# Built in conversion functions follow ...
#

def cm2deg(cm, monitor, correctFlat=False):
    """Convert size in cm to size in degrees for a given Monitor object"""
    #check we have a monitor
    if not isinstance(monitor, monitors.Monitor):
        raise ValueError("cm2deg requires a monitors.Monitor object as the second argument but received %s" %str(type(monitor)))
    #get monitor dimensions
    dist = monitor.getDistance()
    #check they all exist
    if dist==None:
        raise ValueError("Monitor %s has no known distance (SEE MONITOR CENTER)" %monitor.name)
    if correctFlat:
        return np.arctan(np.radians(cm/dist))
    else:
        return cm/(dist*0.017455)

def deg2cm(degrees, monitor, correctFlat=False):
    """Convert size in degrees to size in pixels for a given Monitor object.

    If `correctFlat==False` then the screen will be treated as if all points are
    equal distance from the eye. This means that each "degree" will be the same
    size irrespective of its position.

    If `correctFlat==True` then the `degrees` argument must be an Nx2 matrix for X and Y values
    (the two cannot be calculated separately in this case).

    With correctFlat==True the positions may look strange because more eccentric vertices will be spaced further apart.
    """
    #check we have a monitor
    if not hasattr(monitor, 'getDistance'):
        raise ValueError("deg2cm requires a monitors.Monitor object as the second argument but received %s" %str(type(monitor)))
    #get monitor dimensions
    dist = monitor.getDistance()
    #check they all exist
    if dist==None:
        raise ValueError("Monitor %s has no known distance (SEE MONITOR CENTER)" %monitor.name)
    rads = radians(degrees)
    if correctFlat:
        if len(degrees.shape)<2 or degrees.shape[1]!=2:
            raise ValueError("If using deg2cm with correctedFlat==True then degrees arg must have shape [N,2], not %s" %degrees.shape)
        cmXY = np.zeros(degrees.shape, 'f')
        cmXY[:,0] = hypot(dist, tan(rads[:,1])*dist) * tan(rads[:,0])
        cmXY[:,1] = hypot(dist, tan(rads[:,0])*dist) * tan(rads[:,1])
        # derivation:
        #    if hypotY is line from eyeball to [x,0] given by hypot(dist, tan(degX))
        #    then cmY is distance from [x,0] to [x,y] given by hypotY*tan(degY)
        #    similar for hypotX to get cmX
        # alternative:
        #    we could do this by converting to polar coords, converting to cm and then
        #    going back to cartesian, but this would be slower(?)
        return cmXY
    else:
        return degrees*dist*0.017455 #the size of 1 deg at screen centre

def cm2pix(cm, monitor):
    """Convert size in degrees to size in pixels for a given Monitor object"""
    #check we have a monitor
    if not isinstance(monitor, monitors.Monitor):
        raise ValueError("cm2pix requires a monitors.Monitor object as the second argument but received %s" %str(type(monitor)))
    #get monitor params and raise error if necess
    scrWidthCm = monitor.getWidth()
    scrSizePix = monitor.getSizePix()
    if scrSizePix==None:
        raise ValueError("Monitor %s has no known size in pixels (SEE MONITOR CENTER)" %monitor.name)
    if scrWidthCm==None:
        raise ValueError("Monitor %s has no known width in cm (SEE MONITOR CENTER)" %monitor.name)

    return cm*scrSizePix[0]/float(scrWidthCm)


def pix2cm(pixels, monitor):
    """Convert size in pixels to size in cm for a given Monitor object"""
    #check we have a monitor
    if not isinstance(monitor, monitors.Monitor):
        raise ValueError("cm2pix requires a monitors.Monitor object as the second argument but received %s" %str(type(monitor)))
    #get monitor params and raise error if necess
    scrWidthCm = monitor.getWidth()
    scrSizePix = monitor.getSizePix()
    if scrSizePix==None:
        raise ValueError("Monitor %s has no known size in pixels (SEE MONITOR CENTER)" %monitor.name)
    if scrWidthCm==None:
        raise ValueError("Monitor %s has no known width in cm (SEE MONITOR CENTER)" %monitor.name)
    return pixels*float(scrWidthCm)/scrSizePix[0]

def deg2pix(degrees, monitor, correctFlat=False):
    """Convert size in degrees to size in pixels for a given Monitor object"""
    #get monitor params and raise error if necess
    scrWidthCm = monitor.getWidth()
    scrSizePix = monitor.getSizePix()
    if scrSizePix==None:
        raise ValueError("Monitor %s has no known size in pixels (SEE MONITOR CENTER)" %monitor.name)
    if scrWidthCm==None:
        raise ValueError("Monitor %s has no known width in cm (SEE MONITOR CENTER)" %monitor.name)

    cmSize = deg2cm(degrees, monitor, correctFlat)
    return cmSize*scrSizePix[0]/float(scrWidthCm)

def pix2deg(pixels, monitor, correctFlat=False):
    """Convert size in pixels to size in degrees for a given Monitor object"""
    #get monitor params and raise error if necess
    scrWidthCm = monitor.getWidth()
    scrSizePix = monitor.getSizePix()
    if scrSizePix==None:
        raise ValueError("Monitor %s has no known size in pixels (SEE MONITOR CENTER)" %monitor.name)
    if scrWidthCm==None:
        raise ValueError("Monitor %s has no known width in cm (SEE MONITOR CENTER)" %monitor.name)
    cmSize=pixels*float(scrWidthCm)/scrSizePix[0]
    return cm2deg(cmSize, monitor, correctFlat)
