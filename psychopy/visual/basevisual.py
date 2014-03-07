#!/usr/bin/env python2

'''A base class that is subclassed to produce specific visual stimuli'''

# Part of the PsychoPy library
# Copyright (C) 2014 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

import copy

import psychopy  # so we can get the __path__
from psychopy import logging

# tools must only be imported *after* event or MovieStim breaks on win32
# (JWP has no idea why!)
from psychopy.tools.arraytools import val2array
from psychopy.tools.attributetools import attributeSetter, setWithOperation
from psychopy.tools.colorspacetools import dkl2rgb, lms2rgb
from psychopy.tools.monitorunittools import cm2pix, deg2pix, pix2cm, pix2deg, convertToPix
from psychopy.visual.helpers import (pointInPolygon, polygonsOverlap,
                                     setColor, setTexIfNoShaders)

import numpy

global currWindow
currWindow = None

from psychopy.constants import NOT_STARTED, STARTED, STOPPED

"""
There are three 'levels' of base visual stim classes:
  - MinimalStim:          non-visual house-keeping code common to all visual stim (name, autoLog, etc)
  - LegacyBaseVisualStim: extends Minimal, adds deprecated visual methods (eg, setRGB)
  - BaseVisualStim:       extends Legacy, adds current / preferred visual methods
"""

class MinimalStim(object):
    """Non-visual methods and attributes for BaseVisualStim and RatingScale.

    Includes: name, autoDraw, autoLog, status, __str__
    """
    def __init__(self, name='', autoLog=True):
        self.name = name
        self.status = NOT_STARTED
        self.autoLog = autoLog
        if self.autoLog:
            logging.warning("%s is calling MinimalStim.__init__() with autolog=True. Set autoLog to True only at the end of __init__())" \
                            %(self.__class__.__name__))

    def __str__(self, complete=False):
        """
        """
        if hasattr(self, '_initParams'):
            className = self.__class__.__name__
            paramStrings = []
            for param in self._initParams:
                if hasattr(self, param):
                    val = getattr(self, param)
                    valStr = repr(getattr(self, param))
                    if len(repr(valStr))>50 and not complete:
                        if val.__class__.__name__ == 'attributeSetter':
                            valStr = "%s(...)" %val.__getattribute__.__class__.__name__
                        else:
                            valStr = "%s(...)" %val.__class__.__name__
                else:
                    valStr = 'UNKNOWN'
                paramStrings.append("%s=%s" %(param, valStr))
            #this could be used if all params are known to exist:
            # paramStrings = ["%s=%s" %(param, getattr(self, param)) for param in self._initParams]
            params = ", ".join(paramStrings)
            s = "%s(%s)" %(className, params)
        else:
            s = object.__repr__(self)
        return s

    # Might seem simple at first, but this ensures that "name" attribute
    # appears in docs and that name setting and updating is logged.
    @attributeSetter
    def name(self, value):
        """The name of the object to be using during logged messages about
        this stim. If you have multiple stimuli in your experiment this really
        helps to make sense of log files!

        type: String

        Example::

            upper = visual.TextStim(win, text='Monty', name='upperStim')
            lower = visual.TextStim(win, text='Python', name='lowerStim')
            upper.setAutoDraw(True)
            for frameN in range(3):
                win.flip()
            # turn off top and turn on bottom
            upper.setAutoDraw(False)
            lower.setAutoDraw(True)
            for frameN in range(3):
                win.flip()
            # log file will include names to identify which stim came on/off
        """
        self.__dict__['name'] = value

    @attributeSetter
    def autoDraw(self, value):
        """Determines whether the stimulus should be automatically drawn on

        Value should be: `True` or `False`

        You do NOT need to set this on every frame flip!
        """
        self.__dict__['autoDraw'] = value
        toDraw = self.win._toDraw
        toDrawDepths = self.win._toDrawDepths
        beingDrawn = (self in toDraw)
        if value == beingDrawn:
            return #nothing to do
        elif value:
            #work out where to insert the object in the autodraw list
            depthArray = numpy.array(toDrawDepths)
            iis = numpy.where(depthArray < self.depth)[0]#all indices where true
            if len(iis):#we featured somewhere before the end of the list
                toDraw.insert(iis[0], self)
                toDrawDepths.insert(iis[0], self.depth)
            else:
                toDraw.append(self)
                toDrawDepths.append(self.depth)
            self.status = STARTED
        elif value == False:
            #remove from autodraw lists
            toDrawDepths.pop(toDraw.index(self))  #remove from depths
            toDraw.remove(self)  #remove from draw list
            self.status = STOPPED

    def setAutoDraw(self, value, log=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message"""
        self.autoDraw = value

    @attributeSetter
    def autoLog(self, value):
        """Whether every change in this stimulus should be logged automatically

        Value should be: `True` or `False`

        Set this to `False` if your stimulus is updating frequently (e.g.
        updating its position every frame) or you will swamp the log file with
        messages that aren't likely to be useful.
        """
        self.__dict__['autoLog'] = value

    def setAutoLog(self, value=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message"""
        self.autoLog = value


class LegacyBaseVisualStim(MinimalStim):
    """Class to hold deprecated visual methods and attributes.

    Intended only for use as a base class for BaseVisualStim, to maintain
    backwards compatibility while reducing clutter in class BaseVisualStim.
    """
    def _calcSizeRendered(self):
        """DEPRECATED in 1.80.00. This funtionality is now handled by _updateVertices() and verticesPix"""
        #raise DeprecationWarning, "_calcSizeRendered() was deprecated in 1.80.00. This funtionality is nowhanded by _updateVertices() and verticesPix"
        if self.units in ['norm','pix', 'height']: self._sizeRendered=copy.copy(self.size)
        elif self.units in ['deg', 'degs']: self._sizeRendered=deg2pix(self.size, self.win.monitor)
        elif self.units=='cm': self._sizeRendered=cm2pix(self.size, self.win.monitor)
        else:
            logging.ERROR("Stimulus units should be 'height', 'norm', 'deg', 'cm' or 'pix', not '%s'" %self.units)

    def _calcPosRendered(self):
        """DEPRECATED in 1.80.00. This funtionality is now handled by _updateVertices() and verticesPix"""
        #raise DeprecationWarning, "_calcSizeRendered() was deprecated in 1.80.00. This funtionality is now handled by _updateVertices() and verticesPix"
        if self.units in ['norm','pix', 'height']: self._posRendered= copy.copy(self.pos)
        elif self.units in ['deg', 'degs']: self._posRendered=deg2pix(self.pos, self.win.monitor)
        elif self.units=='cm': self._posRendered=cm2pix(self.pos, self.win.monitor)

    def setDKL(self, newDKL, operation=''):
        """DEPRECATED since v1.60.05: Please use the `color` attribute
        """
        self._set('dkl', val=newDKL, op=operation)
        self.setRGB(dkl2rgb(self.dkl, self.win.dkl_rgb))
    def setLMS(self, newLMS, operation=''):
        """DEPRECATED since v1.60.05: Please use the `color` attribute
        """
        self._set('lms', value=newLMS, op=operation)
        self.setRGB(lms2rgb(self.lms, self.win.lms_rgb))
    def setRGB(self, newRGB, operation=''):
        """DEPRECATED since v1.60.05: Please use the `color` attribute
        """
        self._set('rgb', newRGB, operation)
        setTexIfNoShaders(self)

    @attributeSetter
    def depth(self, value):
        """
        Deprecated. Depth is now controlled simply by drawing order.
        """
        self.__dict__['depth'] = value


class BaseVisualStim(LegacyBaseVisualStim):
    """A template for a visual stimulus class.

    Actual visual stim like GratingStim, TextStim etc... are based on this.
    Not finished...?
    """
    def __init__(self, win, units=None, name='', autoLog=True):
        self.autoLog = False  # just to start off during init, set at end
        self.win = win
        self.units = units
        self._verticesBase = [[0.5,-0.5],[-0.5,-0.5],[-0.5,0.5],[0.5,0.5]] #sqr
        self._rotationMatrix = [[1.,0.],[0.,1.]] #no rotation as a default
        # self.autoLog is set at end of MinimalStim.__init__
        LegacyBaseVisualStim.__init__(self, name=name, autoLog=autoLog)
        if self.autoLog:
            logging.warning("%s is calling BaseVisualStim.__init__() with autolog=True. Set autoLog to True only at the end of __init__())" \
                            %(self.__class__.__name__))

    @attributeSetter
    def win(self, value):
        """ The :class:`~psychopy.visual.Window` object in which the stimulus will be rendered
        by default. (required)

       Example, drawing same stimulus in two different windows and display
       simultaneously. Assuming that you have two windows and a stimulus (win1, win2 and stim)::

           stim.win = win1  # stimulus will be drawn in win1
           stim.draw()  # stimulus is now drawn to win1
           stim.win = win2  # stimulus will be drawn in win2
           stim.draw()  # it is now drawn in win2
           win1.flip(waitBlanking=False)  # do not wait for next monitor update
           win2.flip()  # wait for vertical blanking.

        """
        self.__dict__['win'] = value

    @attributeSetter
    def units(self, value):
        """
        None, 'norm', 'cm', 'deg' or 'pix'

        If None then the current units of the :class:`~psychopy.visual.Window` will be used.
        See :ref:`units` for explanation of other options.

        Note that when you change units, you don't change the stimulus parameters
        and it is likely to change appearance. Example::

            # This stimulus is 20% wide and 50% tall with respect to window
            stim = visual.PatchStim(win, units='norm', size=(0.2, 0.5)

            # This stimulus is 0.2 degrees wide and 0.5 degrees tall.
            stim.units = 'deg'
        """
        if value != None and len(value):
            self.__dict__['units'] = value
        else:
            self.__dict__['units'] = self.win.units

        # Update size and position if they are defined. If not, this is probably
        # during some init and they will be defined later, given the new unit.
        if not isinstance(self.size, attributeSetter) and not isinstance(self.pos, attributeSetter):
            self.size = self.size
            self.pos = self.pos

    @attributeSetter
    def opacity(self, value):
        """Determines how visible the stimulus is relative to background

        The value should be a single float ranging 1.0 (opaque) to 0.0
        (transparent).
        :ref:`Operations <attrib-operations>` are supported.

        Precisely how this is used depends on the :ref:`blendMode`
        """
        self.__dict__['opacity'] = value

        if not 0 <= value <= 1 and self.autoLog:
            logging.warning('Setting opacity outside range 0.0 - 1.0 has no additional effect')

        #opacity is coded by the texture, if not using shaders
        if hasattr(self, 'useShaders') and not self.useShaders:
            if hasattr(self,'mask'):
                self.mask = self.mask

    @attributeSetter
    def contrast(self, value):
        """A value that is simply multiplied by the color

        Value should be: a float between -1 (negative) and 1 (unchanged).
            :ref:`Operations <attrib-operations>` supported.

        Set the contrast of the stimulus, i.e. scales how far the stimulus
        deviates from the middle grey. You can also use the stimulus
        `opacity` to control contrast, but that cannot be negative.

        Examples::

            stim.contrast = 1.0  # unchanged contrast
            stim.contrast = 0.5  # decrease contrast
            stim.contrast = 0.0  # uniform, no contrast
            stim.contrast = -0.5 # slightly inverted
            stim.contrast = -1   # totally inverted

        Setting contrast outside range -1 to 1 is permitted, but may
        produce strange results if color values exceeds the monitor limits.::

            stim.contrast = 1.2 # increases contrast.
            stim.contrast = -1.2  # inverts with increased contrast
        """
        self.__dict__['contrast'] = value

        # If we don't have shaders we need to rebuild the stimulus
        if hasattr(self, 'useShaders'):
            if not self.useShaders:
                if self.__class__.__name__ == 'TextStim':
                    self.setText(self.text)
                if self.__class__.__name__ == 'ImageStim':
                    self.setImage(self._imName)
                if self.__class__.__name__ in ('GratingStim', 'RadialStim'):
                    self.tex = self.tex
                if self.__class__.__name__ in ('ShapeStim','DotStim'):
                    pass # They work fine without shaders?
                elif self.autoLog:
                    logging.warning('Tried to set contrast while useShaders = False but stimulus was not rebuild. Contrast might remain unchanged.')
        elif self.autoLog:
            logging.warning('Contrast was set on class where useShaders was undefined. Contrast might remain unchanged')

    @attributeSetter
    def useShaders(self, value):
        """Should shaders be used to render the stimulus (typically leave as `True`)

        If the system support the use of OpenGL shader language then leaving
        this set to True is highly recommended. If shaders cannot be used then
        various operations will be slower (notably, changes to stimulus color
        or contrast)
        """
        #NB TextStim overrides this function, so changes here may need changing there too
        self.__dict__['useShaders'] = value
        if value == True and self.win._haveShaders == False:
            logging.error("Shaders were requested but aren't available. Shaders need OpenGL 2.0+ drivers")
        if value != self.useShaders:
            self.useShaders = value
            if hasattr(self,'tex'):
                self.tex = self.tex
            elif hasattr(self,'_imName'):
                self.setIm(self._imName, log=False)
            self.mask = self.mask
            self._needUpdate = True

    @attributeSetter
    def ori(self, value):
        """The orientation of the stimulus (in degrees).

        Should be a single value (:ref:`scalar <attrib-scalar>`). :ref:`Operations <attrib-operations>` are supported.

        Orientation convention is like a clock: 0 is vertical, and positive
        values rotate clockwise. Beyond 360 and below zero values wrap
        appropriately.

        """
        self.__dict__['ori'] = value
        radians = value*0.017453292519943295
        self._rotationMatrix = numpy.array([[numpy.cos(radians), -numpy.sin(radians)],
                                [numpy.sin(radians), numpy.cos(radians)]])
        self._needVertexUpdate=True #need to update update vertices
        self._needUpdate = True

    @attributeSetter
    def size(self, value):
        """The size (w,h) of the stimulus in the stimulus :ref:`units <units>`

        Value should be :ref:`x,y-pair <attrib-xy>`, :ref:`scalar <attrib-scalar>` (applies to both dimensions)
        or None (resets to default). :ref:`Operations <attrib-operations>` are supported.

        Sizes can be negative (causing a mirror-image reversal) and can extend beyond the window.

        Example::

            stim.size = 0.8  # Set size to (xsize, ysize) = (0.8, 0.8), quadratic.
            print stim.size  # Outputs array([0.8, 0.8])
            stim.size += (0.5, -0.5)  # make wider and flatter. Is now (1.3, 0.3)

        Tip: if you can see the actual pixel range this corresponds to by
        looking at `stim._sizeRendered`
        """
        value = val2array(value)  # Check correct user input
        self._requestedSize = value  #to track whether we're just using a default
        # None --> set to default
        if value == None:
            """Set the size to default (e.g. to the size of the loaded image etc)"""
            #calculate new size
            if self._origSize is None:  #not an image from a file
                value = numpy.array([0.5, 0.5])  #this was PsychoPy's original default
            else:
                #we have an image - calculate the size in `units` that matches original pixel size
                if self.units == 'pix':
                    value = numpy.array(self._origSize)
                elif self.units in ['deg', 'degFlatPos', 'degFlat']:
                    #NB when no size has been set (assume to use orig size in pix) this should not
                    #be corrected for flat anyway, so degFlat==degFlatPos
                    value = pix2deg(numpy.array(self._origSize, float), self.win.monitor)
                elif self.units == 'norm':
                    value = 2 * numpy.array(self._origSize, float) / self.win.size
                elif self.units == 'height':
                    value = numpy.array(self._origSize, float) / self.win.size[1]
                elif self.units == 'cm':
                    value = pix2cm(numpy.array(self._origSize, float), self.win.monitor)
                else:
                    raise AttributeError, "Failed to create default size for ImageStim. Unsupported unit, %s" %(repr(self.units))
        self.__dict__['size'] = value
        self._needVertexUpdate=True
        self._needUpdate = True
        if hasattr(self, '_calcCyclesPerStim'):
            self._calcCyclesPerStim()

    @attributeSetter
    def pos(self, value):
        """The position of the center of the stimulus in the stimulus :ref:`units <units>`

        Value should be an :ref:`x,y-pair <attrib-xy>`. :ref:`Operations <attrib-operations>`
        are also supported.

        Example::

            stim.pos = (0.5, 0)  # Set slightly to the right of center
            stim.pos += (0.5, -1)  # Increment pos rightwards and upwards. Is now (1.0, -1.0)
            stim.pos *= 0.2  # Move stim towards the center. Is now (0.2, -0.2)

        Tip: if you can see the actual pixel range this corresponds to by
        looking at `stim._posRendered`
        """
        self.__dict__['pos'] = val2array(value, False, False)
        self._needVertexUpdate=True
        self._needUpdate = True

    @attributeSetter
    def color(self, value):
        """Color of the stimulus

        Value should be one of:
            + string: to specify a :ref:`colorNames` or :ref:`hexColors`
            + numerically: (scalar or triplet) for DKL, RGB or other :ref:`colorspaces`. For
                these, :ref:`operations <attrib-operations>` are supported.

        When color is specified using numbers, it is interpreted with
        respect to the stimulus' current colorSpace. If color is given as a
        single value (scalar) then this wil be applied to all 3 channels.

        Examples::

                myStim.color = 'white'
                myStim.color = 'RoyalBlue'  #(the case is actually ignored)
                myStim.color = '#DDA0DD'  #DDA0DD is hexadecimal for plum
                myStim.color = [1.0,-1.0,-1.0]  #if colorSpace='rgb': a red color in rgb space
                myStim.color = [0.0,45.0,1.0] #if colorSpace='dkl': DKL space with elev=0, azimuth=45
                myStim.color = [0,0,255] #if colorSpace='rgb255': a blue stimulus using rgb255 space


        :ref:`Operations <attrib-operations>` work as normal. For example,
        assuming that colorSpace='rgb'::

            thisStim.color += [1,1,1]  #increment all guns by 1 value
            thisStim.color *= -1  #multiply the color by -1 (which in this space inverts the contrast)
            thisStim.color *= [0.5, 0, 1]  #decrease red, remove green, keep blue
        """
        setColor(self, value, rgbAttrib='rgb', colorAttrib='color')

    @attributeSetter
    def colorSpace(self, value):
        """The name of the color space currently being used (for numeric colors)

        Value should be: a string or None

        For strings and hex values this is not needed.
        If None the default colorSpace for the stimulus is
        used (defined during initialisation).

        Please note that changing colorSpace does not change stimulus parameters. Example::

            # A light green text
            stim = visual.TextStim(win, 'Color me!', color=(0, 1, 0), colorSpace='rgb')

            # An almost-black text
            stim.colorSpace = 'rgb255'

            # Make it light green again
            stim.color = (128, 255, 128)
        """
        self.__dict__['colorSpace'] = value

    def draw(self):
        raise NotImplementedError('Stimulus classes must overide visual.BaseVisualStim.draw')

    def setPos(self, newPos, operation='', log=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message
        """
        self._set('pos', val=newPos, op=operation, log=log)
    def setDepth(self, newDepth, operation='', log=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message
        """
        self._set('depth', newDepth, operation, log)
    def setSize(self, newSize, operation='', units=None, log=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message
        """
        if units==None: units=self.units#need to change this to create several units from one
        self._set('size', newSize, op=operation, log=log)
    def setOri(self, newOri, operation='', log=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message
        """
        self._set('ori',val=newOri, op=operation, log=log)
    def setOpacity(self, newOpacity, operation='', log=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message
        """
        self._set('opacity', newOpacity, operation, log=log)
    def setContrast(self, newContrast, operation='', log=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message
        """
        self._set('contrast', newContrast, operation, log=log)
    def setColor(self, color, colorSpace=None, operation='', log=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message
        """
        setColor(self,color, colorSpace=colorSpace, operation=operation,
                    rgbAttrib='rgb', #or 'fillRGB' etc
                    colorAttrib='color',
                    log=log)
    def _set(self, attrib, val, op='', log=True):
        """
        Deprecated. Use methods specific to the parameter you want to set

        e.g. ::

             stim.pos = [3,2.5]
             stim.ori = 45
             stim.phase += 0.5

        NB this method does not flag the need for updates any more - that is
        done by specific methods as described above.
        """
        if op==None: op=''
        #format the input value as float vectors
        if type(val) in [tuple, list, numpy.ndarray]:
            val = val2array(val)

        # Handle operations
        setWithOperation(self, attrib, val, op)

        if log and self.autoLog:
            self.win.logOnFlip("Set %s %s=%s" %(self.name, attrib, getattr(self,attrib)),
                level=logging.EXP,obj=self)

    def setUseShaders(self, value=True):
        """Usually you can use 'stim.attribute = value' syntax instead,
        but use this method if you need to suppress the log message"""
        self.useShaders = value
    def _selectWindow(self, win):
        global currWindow
        #don't call switch if it's already the curr window
        if win!=currWindow and win.winType=='pyglet':
            win.winHandle.switch_to()
            currWindow = win

    def _updateList(self):
        """
        The user shouldn't need this method since it gets called
        after every call to .set()
        Chooses between using and not using shaders each call.
        """
        if self.useShaders:
            self._updateListShaders()
        else:
            self._updateListNoShaders()

    @property
    def verticesPix(self):
        """This determines the coordinates of the vertices for the
        current stimulus in pixels, accounting for size, ori, pos and units
        """
        #because this is a property getter we can check /on-access/ if it needs updating :-)
        if self._needVertexUpdate:
            self._updateVertices()
        return self.__dict__['verticesPix']
    def _updateVertices(self):
        """Sets Stim.verticesPix from pos and size
        """
        if hasattr(self, 'vertices'):
            verts = self.vertices
        else:
            verts = self._verticesBase
        #check wheher stimulus needs flipping in either direction
        flip = numpy.array([1,1])
        if hasattr(self, 'flipHoriz'):
            flip[0] = self.flipHoriz*(-2)+1#True=(-1), False->(+1)
        if hasattr(self, 'flipVert'):
            flip[1] = self.flipVert*(-2)+1#True=(-1), False->(+1)
        # set size and orientation
        verts = numpy.dot(self.size*verts*flip, self._rotationMatrix)
        #then combine with position and convert to pix
        verts = convertToPix(vertices=verts, pos=self.pos, win=self.win, units=self.units)
        #assign to self attrbute
        self.__dict__['verticesPix'] = verts
        self._needVertexUpdate = False
        self._needUpdate = True #but we presumably need to update the list
    def contains(self, x, y=None, units=None):
        """Determines if a point x,y is inside the extent of the stimulus.

        Can accept variety of input options:
            + two separate args, x and y
            + one arg (list, tuple or array) containing two vals (x,y)
            + an object with a getPos() method that returns x,y, such
                as a :class:`~psychopy.event.Mouse`. Returns `True` if the point is
                within the area defined by `vertices`.

        This method handles complex shapes, including concavities and self-crossings.

        Note that, if your stimulus uses a mask (such as a Gaussian blob) then
        this is not accounted for by the `contains` method; the extent of the
        stmulus is determined purely by the size, pos and orientation settings
        (and by the vertices for shape stimuli).

        See coder demo, shapeContains.py
        """
        #get the object in pixels
        if hasattr(x, 'verticesPix'):
            xy = x.verticesPix #access only once - this is a property (slower to access)
            units = 'pix' #we can forget about the units
        elif hasattr(x, 'getPos'):
            xy = x.getPos()
            units = x.units
        elif type(x) in [list, tuple, numpy.ndarray]:
            xy = numpy.array(x)
        else:
            xy = numpy.array((x,y))
        #try to work out what units x,y has
        if units is None:
            if hasattr(xy, 'units'):
                units = xy.units
            else:
                units = self.units
        if units != 'pix':
            xy = convertToPix(xy, pos=0, units=units, win=self.win)
        # ourself in pixels
        selfVerts = self.verticesPix
        return pointInPolygon(xy[0], xy[1], poly = selfVerts)

    def _getPolyAsRendered(self):
        """return a list of vertices as rendered; used by overlaps()
        """
        oriRadians = numpy.radians(self.ori)
        sinOri = numpy.sin(-oriRadians)
        cosOri = numpy.cos(-oriRadians)
        x = self._verticesRendered[:,0] * cosOri - self._verticesRendered[:,1] * sinOri
        y = self._verticesRendered[:,0] * sinOri + self._verticesRendered[:,1] * cosOri
        return numpy.column_stack((x,y)) + self._posRendered

    def overlaps(self, polygon):
        """Determines if this stimulus intersects another one. If `polygon` is
        another stimulus instance, then the vertices and location of that stimulus
        will be used as the polygon. Overlap detection is only approximate; it
        can fail with pointy shapes. Returns `True` if the two shapes overlap.

        Note that, if your stimulus uses a mask (such as a Gaussian blob) then
        this is not accounted for by the `overlaps` method; the extent of the
        stimulus is determined purely by the size, pos, and orientation settings
        (and by the vertices for shape stimuli).

        See coder demo, shapeContains.py
        """
        return polygonsOverlap(self, polygon)

    def _getDesiredRGB(self, rgb, colorSpace, contrast):
        """ Convert color to RGB while adding contrast
        Requires self.rgb, self.colorSpace and self.contrast"""
        # Ensure that we work on 0-centered color (to make negative contrast values work)
        if colorSpace not in ['rgb', 'dkl', 'lms', 'hsv']:
            rgb = (rgb / 255.0) * 2 - 1

        # Convert to RGB in range 0:1 and scaled for contrast
        # NB glColor will clamp it to be 0-1 (whether or not we use FBO)
        desiredRGB = (rgb * contrast + 1) / 2.0
        if not self.win.useFBO:
            # Check that boundaries are not exceeded. If we have an FBO that can handle this
            if numpy.any(desiredRGB > 1.0) or numpy.any(desiredRGB < 0):
                logging.warning('Desired color %s (in RGB 0->1 units) falls outside the monitor gamut. Drawing blue instead' %desiredRGB) #AOH
                desiredRGB=[0.0, 0.0, 1.0]

        return desiredRGB
