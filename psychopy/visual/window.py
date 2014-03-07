#!/usr/bin/env python2

'''A class representing a window for displaying one or more stimuli'''

# Part of the PsychoPy library
# Copyright (C) 2014 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

import sys
import os

# Ensure setting pyglet.options['debug_gl'] to False is done prior to any
# other calls to pyglet or pyglet submodules, otherwise it may not get picked
# up by the pyglet GL engine and have no effect.
# Shaders will work but require OpenGL2.0 drivers AND PyOpenGL3.0+
import pyglet
pyglet.options['debug_gl'] = False
GL = pyglet.gl
import ctypes

#try to find avbin (we'll overload pyglet's load_library tool and then add some paths)
import pyglet.lib
import _pygletLibOverload
pyglet.lib.load_library = _pygletLibOverload.load_library
#on windows try to load avbin now (other libs can interfere)
if sys.platform == 'win32':
    #make sure we also check in SysWOW64 if on 64-bit windows
    if 'C:\\Windows\\SysWOW64' not in os.environ['PATH']:
        os.environ['PATH'] += ';C:\\Windows\\SysWOW64'

    try:
        from pyglet.media import avbin
        haveAvbin = True
    except ImportError:
        # either avbin isn't installed or scipy.stats has been imported
        # (prevents avbin loading)
        haveAvbin = False

import psychopy  # so we can get the __path__
from psychopy import core, platform_specific, logging, prefs, monitors, event
import psychopy.event

# tools must only be imported *after* event or MovieStim breaks on win32
# (JWP has no idea why!)
from psychopy.tools.arraytools import val2array
from psychopy import makeMovies
from psychopy.visual.text import TextStim
from psychopy.visual.grating import GratingStim
from psychopy.visual.helpers import setColor

try:
    from PIL import Image
except ImportError:
    import Image

if sys.platform == 'win32' and not haveAvbin:
    logging.error("""avbin.dll failed to load.
                     Try importing psychopy.visual as the first library
                     (before anything that uses scipy)
                     and make sure that avbin is installed.""")

import numpy

from psychopy.core import rush

global currWindow
currWindow = None
reportNDroppedFrames = 5  # stop raising warning after this

from psychopy.gamma import getGammaRamp, setGammaRamp, setGamma
#import pyglet.gl, pyglet.window, pyglet.image, pyglet.font, pyglet.event
import psychopy._shadersPyglet as _shaders
try:
    from pyglet import media
    havePygletMedia = True
except:
    havePygletMedia = False

try:
    import pygame
except:
    pass

global DEBUG
DEBUG = False

global IOHUB_ACTIVE
IOHUB_ACTIVE = False

#keep track of windows that have been opened
openWindows = []

# can provide a default window for mouse
psychopy.event.visualOpenWindows = openWindows


class Window:
    """Used to set up a context in which to draw objects,
    using either PyGame (python's SDL binding) or pyglet.

    The pyglet backend allows multiple windows to be created, allows the user
    to specify which screen to use (if more than one is available, duh!) and
    allows movies to be rendered.

    Pygame has fewer bells and whistles, but does seem a little faster in text
    rendering. Pygame is used for all sound production and for monitoring the
    joystick.

    """
    def __init__(self,
                 size=(800, 600),
                 pos=None,
                 color=(0, 0, 0),
                 colorSpace='rgb',
                 rgb = None,
                 dkl=None,
                 lms=None,
                 fullscr=None,
                 allowGUI=None,
                 monitor=dict([]),
                 bitsMode=None,
                 winType=None,
                 units=None,
                 gamma = None,
                 blendMode='avg',
                 screen=0,
                 viewScale=None,
                 viewPos=None,
                 viewOri=0.0,
                 waitBlanking=True,
                 allowStencil=False,
                 stereo=False,
                 name='window1',
                 checkTiming=True,
                 useFBO=False,
                 autoLog=True):
        """
        :Parameters:

            size : (800,600)
                Size of the window in pixels (X,Y)
            pos : *None* or (x,y)
                Location of the window on the screen
            rgb : [0,0,0]
                Color of background as [r,g,b] list or single value.
                Each gun can take values betweeen -1 and 1
            fullscr : *None*, True or False
                Better timing can be achieved in full-screen mode
            allowGUI :  *None*, True or False (if None prefs are used)
                If set to False, window will be drawn with no frame and
                no buttons to close etc...
            winType :  *None*, 'pyglet', 'pygame'
                If None then PsychoPy will revert to user/site preferences
            monitor : *None*, string or a `~psychopy.monitors.Monitor` object
                The monitor to be used during the experiment
            units :  *None*, 'height' (of the window), 'norm' (normalised),
                'deg', 'cm', 'pix'
                Defines the default units of stimuli drawn in the window
                (can be overridden by each stimulus)
                See :ref:`units` for explanation of options.
            screen : *0*, 1 (or higher if you have many screens)
                Specifies the physical screen that stimuli will appear on
                (pyglet winType only)
            viewScale : *None* or [x,y]
                Can be used to apply a custom scaling to the current units
                of the :class:`~psychopy.visual.Window`.
            viewPos : *None*, or [x,y]
                If not None, redefines the origin for the window
            viewOri : *0* or any numeric value
                A single value determining the orientation of the view in degs
            waitBlanking : *None*, True or False.
                After a call to flip() should we wait for the blank before
                the script continues
            gamma :
                Monitor gamma for linearisation (will use Bits++ if possible).
                Overrides monitor settings
            bitsMode : None, 'fast', ('slow' mode is deprecated).
                Defines how (and if) the Bits++ box will be used.
                'fast' updates every frame by drawing a hidden line on
                the top of the screen.
            allowStencil : True or *False*
                When set to True, this allows operations that use
                the OpenGL stencil buffer
                (notably, allowing the class:`~psychopy.visual.Aperture`
                to be used).
            stereo : True or *False*
                If True and your graphics card supports quad buffers then t
                his will be enabled.
                You can switch between left and right-eye scenes for drawing
                operations using :func:`~psychopy.visual.Window.setBuffer`

            :note: Preferences. Some parameters (e.g. units) can now be given
                default values in the user/site preferences and these will be
                used if None is given here. If you do specify a value here it
                will take precedence over preferences.

        """

        #what local vars are defined (these are the init params) for use by __repr__
        self._initParams = dir()
        for unecess in ['self', 'checkTiming', 'rgb', 'dkl', ]:
            self._initParams.remove(unecess)

        self.name = name
        self.autoLog = autoLog  # to suppress log msg during testing
        self.size = numpy.array(size, numpy.int)
        self.pos = pos
        # this will get overridden once the window is created
        self.winHandle = None
        self.useFBO = useFBO

        self._toLog = []
        self._toCall = []

        # settings for the monitor: local settings (if available) override
        # monitor
        # if we have a monitors.Monitor object (psychopy 0.54 onwards)
        # convert to a Monitor object
        if not monitor:
            self.monitor = monitors.Monitor('__blank__', autoLog=autoLog)
        if isinstance(monitor, basestring):
            self.monitor = monitors.Monitor(monitor, autoLog=autoLog)
        elif hasattr(monitor, 'keys'):
            #convert into a monitor object
            self.monitor = monitors.Monitor('temp',
                                            currentCalib=monitor,
                                            verbose=False, autoLog=autoLog)
        else:
            self.monitor = monitor

        #otherwise monitor will just be a dict
        self.scrWidthCM = self.monitor.getWidth()
        self.scrDistCM = self.monitor.getDistance()

        scrSize = self.monitor.getSizePix()
        if scrSize is None:
            self.scrWidthPIX = None
        else:
            self.scrWidthPIX = scrSize[0]

        if fullscr is None:
            fullscr = prefs.general['fullscr']
        self._isFullScr = fullscr

        if units is None:
            units = prefs.general['units']
        self.units = units

        if allowGUI is None:
            allowGUI = prefs.general['allowGUI']
        self.allowGUI = allowGUI

        self.screen = screen

        # parameters for transforming the overall view
        self.viewScale = val2array(viewScale)
        self.viewPos = val2array(viewPos, True, False)
        self.viewOri = float(viewOri)
        self.stereo = stereo  # use quad buffer if requested (and if possible)

        # setup bits++ if possible
        self.bitsMode = bitsMode  # could be [None, 'fast', 'slow']
        if self.bitsMode is not None:
            from psychopy.hardware.crs import bits
            self.bits = bits.BitsBox(self)
            self.haveBits = True
            if hasattr(self.monitor, 'lineariseLums'):
                #rather than a gamma value we could use bits++ and provide a
                # complete linearised lookup table using
                # monitor.lineariseLums(lumLevels)
                self.gamma = None

        #load color conversion matrices
        self.dkl_rgb = self.monitor.getDKL_RGB()
        self.lms_rgb = self.monitor.getLMS_RGB()

        #set screen color
        self.colorSpace = colorSpace
        if rgb is not None:
            logging.warning("Use of rgb arguments to stimuli are deprecated. "
                            "Please use color and colorSpace args instead")
            color = rgb
            colorSpace = 'rgb'
        elif dkl is not None:
            logging.warning("Use of dkl arguments to stimuli are deprecated. "
                            "Please use color and colorSpace args instead")
            color = dkl
            colorSpace = 'dkl'
        elif lms is not None:
            logging.warning("Use of lms arguments to stimuli are deprecated. "
                            "Please use color and colorSpace args instead")
            color = lms
            colorSpace = 'lms'
        self.setColor(color, colorSpace=colorSpace)

        self.allowStencil = allowStencil
        #check whether FBOs are supported
        if blendMode == 'add' and not self.useFBO:
            logging.warning('User requested a blendmode of "add" but '
                            'framebuffer objects not available.')
            # resort to the simpler blending without float rendering
            self.blendMode = 'avg'
        else:
            self.blendMode = blendMode
            #then set up gl context and then call self.setBlendMode

        #setup context and openGL()
        if winType is None:  # choose the default windowing
            winType = prefs.general['winType']
        self.winType = winType
        self._setupGL()

        self.setBlendMode(self.blendMode)

        # gamma
        self.gamma = gamma
        self._setupGamma()

        self.frameClock = core.Clock()  # from psycho/core
        self.frames = 0  # frames since last fps calc
        self.movieFrames = []  # list of captured frames (Image objects)

        self.recordFrameIntervals = False
        # Allows us to omit the long timegap that follows each time turn it off
        self.recordFrameIntervalsJustTurnedOn = False
        self.nDroppedFrames = 0
        self.frameIntervals = []

        self._toDraw = []
        self._toDrawDepths = []
        self._eventDispatchers = []

        self.lastFrameT = core.getTime()
        self.waitBlanking = waitBlanking
        self._refreshThreshold = 1/1.0  # initial val needed by flip()

        # over several frames with no drawing
        self._monitorFrameRate=None
        self.monitorFramePeriod=0.0 #for testing  when to stop drawing a stim
        if checkTiming:
            self._monitorFrameRate = self.getActualFrameRate()
        if self._monitorFrameRate is not None:
            self.monitorFramePeriod=1.0/self._monitorFrameRate
            self._refreshThreshold = (1.0/self._monitorFrameRate)*1.2
        else:
            self._refreshThreshold = (1.0/60)*1.2  # guess its a flat panel

        global currWindow
        currWindow = self
        openWindows.append(self)

    def __del__(self):
        if self.useFBO:
            GL.glDeleteTextures(1, self.frameTexture)
            GL.glDeleteFramebuffersEXT( 1, self.frameBuffer)

    def __str__(self):
        className = 'Window'
        paramStrings = []
        for param in self._initParams:
            if hasattr(self, param):
                paramStrings.append("%s=%s" %(param, repr(getattr(self, param))))
            else:
                paramStrings.append("%s=UNKNOWN" %(param))
        # paramStrings = ["%s=%s" %(param, getattr(self, param)) for param in self._initParams]
        params = ", ".join(paramStrings)
        s = "%s(%s)" %(className, params)
        return s

    def setRecordFrameIntervals(self, value=True):
        """To provide accurate measures of frame intervals, to determine
        whether frames are being dropped. The intervals are the times between
        calls to `.flip()`. Set to `True` only during the time-critical parts
        of the script. Set this to `False` while the screen is not being
        updated, i.e., during any slow, non-frame-time-critical sections of
        your code, including inter-trial-intervals, `event.waitkeys()`,
        `core.wait()`, or `image.setImage()`.

        see also:
            Window.saveFrameIntervals()
        """
        # was off, and now turning it on
        if not self.recordFrameIntervals and value:
            self.recordFrameIntervalsJustTurnedOn = True
        else:
            self.recordFrameIntervalsJustTurnedOn = False
        self.recordFrameIntervals = value

        self.frameClock.reset()

    def saveFrameIntervals(self, fileName=None, clear=True):
        """Save recorded screen frame intervals to disk, as comma-separated
        values.

        :Parameters:

        fileName : *None* or the filename (including path if necessary) in
        which to store the data.
            If None then 'lastFrameIntervals.log' will be used.

        """
        if not fileName:
            fileName = 'lastFrameIntervals.log'
        if len(self.frameIntervals):
            intervalStr = str(self.frameIntervals)[1:-1]
            f = open(fileName, 'w')
            f.write(intervalStr)
            f.close()
        if clear:
            self.frameIntervals = []
            self.frameClock.reset()

    def onResize(self, width, height):
        '''A default resize event handler.

        This default handler updates the GL viewport to cover the entire
        window and sets the ``GL_PROJECTION`` matrix to be orthagonal in
        window space.  The bottom-left corner is (0, 0) and the top-right
        corner is the width and height of the :class:`~psychopy.visual.Window`
        in pixels.

        Override this event handler with your own to create another
        projection, for example in perspective.
        '''
        if height == 0:
            height = 1
        GL.glViewport(0, 0, width, height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glOrtho(-1, 1, -1, 1, -1, 1)
        #GL.gluPerspective(90, 1.0*width/height, 0.1, 100.0)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

    def logOnFlip(self, msg, level, obj=None):
        """Send a log message that should be time-stamped at the next .flip()
        command.

        :parameters:
            - msg: the message to be logged
            - level: the level of importance for the message
            - obj (optional): the python object that might be associated with
              this message if desired
        """

        self._toLog.append({'msg': msg, 'level': level, 'obj': repr(obj)})

    def callOnFlip(self, function, *args, **kwargs):
        """Call a function immediately after the next .flip() command.

        The first argument should be the function to call, the following args
        should be used exactly as you would for your normal call to the
        function (can use ordered arguments or keyword arguments as normal).

        e.g. If you have a function that you would normally call like this::

            pingMyDevice(portToPing, channel=2, level=0)

        then you could call callOnFlip() to have the function call synchronized
        with the frame flip like this::

            win.callOnFlip(pingMyDevice, portToPing, channel=2, level=0)

        """
        self._toCall.append({'function': function,
                             'args': args,
                             'kwargs': kwargs})

    def flip(self, clearBuffer=True):
        """Flip the front and back buffers after drawing everything for your
        frame. (This replaces the win.update() method, better reflecting what
        is happening underneath).

        win.flip(clearBuffer=True)#results in a clear screen after flipping
        win.flip(clearBuffer=False)#the screen is not cleared (so represent
        the previous screen)
        """
        global currWindow
        for thisStim in self._toDraw:
            thisStim.draw()

        if self.useFBO:
            GL.glUseProgram(self._progFBOtoFrame)
            #need blit the frambuffer object to the actual back buffer

            # unbind the framebuffer as the render target
            GL.glBindFramebufferEXT(GL.GL_FRAMEBUFFER_EXT, 0)
            GL.glDisable(GL.GL_BLEND)

            # before flipping need to copy the renderBuffer to the frameBuffer
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glEnable(GL.GL_TEXTURE_2D)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.frameTexture)
            GL.glColor3f(1.0, 1.0, 1.0)  # glColor multiplies with texture
            #draw the quad for the screen
            GL.glBegin(GL.GL_QUADS)

            GL.glTexCoord2f(0.0, 0.0)
            GL.glVertex2f(-1.0, -1.0)

            GL.glTexCoord2f(0.0, 1.0)
            GL.glVertex2f(-1.0, 1.0)

            GL.glTexCoord2f(1.0, 1.0)
            GL.glVertex2f(1.0, 1.0)

            GL.glTexCoord2f(1.0, 0.0)
            GL.glVertex2f(1.0, -1.0)

            GL.glEnd()
            GL.glEnable(GL.GL_BLEND)
            GL.glUseProgram(0)

        #update the bits++ LUT
        if self.bitsMode in ['fast', 'bits++']:
            self.bits._drawLUTtoScreen()

        if self.winType == "pyglet":
            #make sure this is current context
            if currWindow != self:
                self.winHandle.switch_to()
                currWindow = self

            GL.glTranslatef(0.0, 0.0, -5.0)

            for dispatcher in self._eventDispatchers:
                dispatcher.dispatch_events()

            # this might need to be done even more often than once per frame?
            self.winHandle.dispatch_events()

            # for pyglet 1.1.4 you needed to call media.dispatch for
            # movie updating
            if pyglet.version < '1.2':
                pyglet.media.dispatch_events()  # for sounds to be processed
            self.winHandle.flip()
        else:
            if pygame.display.get_init():
                pygame.display.flip()
                # keeps us in synch with system event queue
                pygame.event.pump()
            else:
                core.quit()  # we've unitialised pygame so quit

        if self.useFBO:
            #set rendering back to the framebuffer object
            GL.glBindFramebufferEXT(GL.GL_FRAMEBUFFER_EXT, self.frameBuffer)
            GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0_EXT)
            GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0_EXT)
            #set to no active rendering texture
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

        #rescale/reposition view of the window
        if self.viewScale is not None:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glLoadIdentity()
            GL.glOrtho(-1, 1, -1, 1, -1, 1)
            GL.glScalef(self.viewScale[0], self.viewScale[1], 1)
        else:
            GL.glLoadIdentity()  # still worth loading identity

        if self.viewPos is not None:
            GL.glMatrixMode(GL.GL_MODELVIEW)
            if not self.viewScale:
                scale = [1, 1]
            else:
                scale = self.viewScale
            norm_rf_pos_x = self.viewPos[0]/scale[0]
            norm_rf_pos_y = self.viewPos[1]/scale[1]
            GL.glTranslatef(norm_rf_pos_x, norm_rf_pos_y, 0.0)

        if self.viewOri is not None:
            GL.glRotatef(self.viewOri, 0.0, 0.0, -1.0)

        #reset returned buffer for next frame
        if clearBuffer:
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        #waitBlanking
        if self.waitBlanking:
            GL.glBegin(GL.GL_POINTS)
            GL.glColor4f(0, 0, 0, 0)
            if sys.platform == 'win32' and self.glVendor.startswith('ati'):
                pass
            else:
                # this corrupts text rendering on win with some ATI cards :-(
                GL.glVertex2i(10, 10)
            GL.glEnd()
            GL.glFinish()

        #get timestamp
        now = logging.defaultClock.getTime()

        # run other functions immediately after flip completes
        for callEntry in self._toCall:
            callEntry['function'](*callEntry['args'], **callEntry['kwargs'])
        del self._toCall[:]

        # do bookkeeping
        if self.recordFrameIntervals:
            self.frames += 1
            deltaT = now - self.lastFrameT
            self.lastFrameT = now
            if self.recordFrameIntervalsJustTurnedOn:  # don't do anything
                self.recordFrameIntervalsJustTurnedOn = False
            else:  # past the first frame since turned on
                self.frameIntervals.append(deltaT)
                if deltaT > self._refreshThreshold:
                    self.nDroppedFrames += 1
                    if self.nDroppedFrames < reportNDroppedFrames:
                        logging.warning('t of last frame was %.2fms (=1/%i)' %
                                        (deltaT*1000, 1/deltaT), t=now)
                    elif self.nDroppedFrames == reportNDroppedFrames:
                        logging.warning("Multiple dropped frames have "
                                        "occurred - I'll stop bothering you "
                                        "about them!")

        #log events
        for logEntry in self._toLog:
            #{'msg':msg,'level':level,'obj':copy.copy(obj)}
            logging.log(msg=logEntry['msg'],
                        level=logEntry['level'],
                        t=now,
                        obj=logEntry['obj'])
        del self._toLog[:]

        #keep the system awake (prevent screen-saver or sleep)
        platform_specific.sendStayAwake()

        #    If self.waitBlanking is True, then return the time that
        # GL.glFinish() returned, set as the 'now' variable. Otherwise
        # return None as before
        #
        if self.waitBlanking is True:
            return now

    def update(self):
        """Deprecated: use Window.flip() instead
        """
        # clearBuffer was the original behaviour for win.update()
        self.flip(clearBuffer=True)

    def multiFlip(self, flips=1, clearBuffer=True):
        """
        Flips multiple times while maintaining display constant.
        Use this method for precise timing.

        :Parameters:

            flips: number of monitor frames to flip image.
                Window.multiFlip(flips=1) is equivalent to Window.flip().

            clearBuffer: as in Window.flip(). This is applied to the last flip.

        Example::

            # Draws myStim1 to buffer
            myStim1.draw()
            # Show stimulus for 4 frames (90 ms at 60Hz)
            myWin.multiFlip(clearBuffer=False, flips=6)
            # Draw myStim2 "on top of" myStim1
            # (because buffer was not cleared above)
            myStim2.draw()
            # Show this for 2 frames (30 ms at 60Hz)
            myWin.multiFlip(flips=2)
            # Show blank screen for 3 frames (because buffer was cleared above)
            myWin.multiFlip(flips=3)
        """

        #Sanity checking
        if flips < 1 and int(flips) == flips:
            logging.error("flips argument for multiFlip should be "
                          "a positive integer")
        if flips > 1 and not self.waitBlanking:
            logging.warning("Call to Window.multiFlip() with flips > 1 is "
                            "unnecessary because Window.waitBlanking=False")

        #Do the flipping with last flip as special case
        for _ in range(flips-1):
            self.flip(clearBuffer=False)
        self.flip(clearBuffer=clearBuffer)

    def setBuffer(self, buffer, clear=True):
        """Choose which buffer to draw to ('left' or 'right').

        Requires the Window to be initialised with stereo=True and requires a
        graphics card that supports quad buffering (e,g nVidia Quadro series)

        PsychoPy always draws to the back buffers, so 'left' will use
        GL_BACK_LEFT This then needs to be flipped once both eye's buffers have
        been  rendered.

        Typical usage::

            win = visual.Window(...., stereo=True)
            while True:
                #clear may not actually be needed
                win.setBuffer('left', clear=True)
                #do drawing for left eye
                win.setBuffer('right', clear=True)
                #do drawing for right eye
                win.flip()

        """
        if buffer == 'left':
            GL.glDrawBuffer(GL.GL_BACK_LEFT)
        elif buffer == 'right':
            GL.glDrawBuffer(GL.GL_BACK_RIGHT)
        else:
            raise "Unknown buffer '%s' requested in Window.setBuffer" % buffer
        if clear:
            self.clearBuffer()

    def clearBuffer(self):
        """Clear the back buffer (to which you are currently drawing) without
        flipping the window. Useful if you want to generate movie sequences
        from the back buffer without actually taking the time to flip the
        window.
        """
        #reset returned buffer for next frame
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

    def getMovieFrame(self, buffer='front'):
        """
        Capture the current Window as an image.
        This can be done at any time (usually after a .flip() command).

        Frames are stored in memory until a .saveMovieFrames(filename) command
        is issued. You can issue getMovieFrame() as often
        as you like and then save them all in one go when finished.

        The back buffer will return the frame that hasn't yet been 'flipped'
        to be visible on screen but has the advantage that the mouse and any
        other overlapping windows won't get in the way.

        The default front buffer is to be called immediately after a win.flip()
        and gives a complete copy of the screen at the window's coordinates.
        """
        im = self._getFrame(buffer=buffer)
        self.movieFrames.append(im)

    def _getFrame(self, buffer='front'):
        """
        Return the current Window as an image.
        """
        #GL.glLoadIdentity()
        #do the reading of the pixels
        if buffer == 'back':
            GL.glReadBuffer(GL.GL_BACK)
        else:
            GL.glReadBuffer(GL.GL_FRONT)

        #fetch the data with glReadPixels
        #pyglet.gl stores the data in a ctypes buffer
        bufferDat = (GL.GLubyte * (4 * self.size[0] * self.size[1]))()
        GL.glReadPixels(0, 0, self.size[0], self.size[1],
                        GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, bufferDat)
        im = Image.fromstring(mode='RGBA', size=self.size, data=bufferDat)

        im = im.transpose(Image.FLIP_TOP_BOTTOM)
        im = im.convert('RGB')

        return im

    def saveMovieFrames(self, fileName, mpgCodec='mpeg1video',
                        fps=30, clearFrames=True):
        """
        Writes any captured frames to disk. Will write any format
        that is understood by PIL (tif, jpg, bmp, png...)

        :parameters:

            filename: name of file, including path (required)
                The extension at the end of the file determines the type of
                file(s) created. If an image type (e.g. .png) is given, then
                multiple static frames are created. If it is .gif then an
                animated GIF image is created (although you will get higher
                quality GIF by saving PNG files and then combining them in
                dedicated image manipulation software, such as GIMP). On
                Windows and Linux `.mpeg` files can be created if `pymedia` is
                installed. On OS X `.mov` files can be created if the
                pyobjc-frameworks-QTKit is installed.

                Unfortunately the libs used for movie generation can be flaky
                and poor quality. As for animated GIFs, better results can be
                achieved by saving as individual .png frames and then combining
                them into a movie using software like ffmpeg.

            mpgCodec: the code to be used **by pymedia** if the filename ends
                in .mpg

            fps: the frame rate to be used throughout the movie **only for
                quicktime (.mov) movies**

            clearFrames: set this to False if you want the frames to be kept
                for additional calls to `saveMovieFrames`

        Examples::

            #writes a series of static frames as frame001.tif,
            # frame002.tif etc...
            myWin.saveMovieFrames('frame.tif')

            # on OS X only
            myWin.saveMovieFrames('stimuli.mov', fps=25)

            # not great quality animated gif
            myWin.saveMovieFrames('stimuli.gif')

            # not on OS X
            myWin.saveMovieFrames('stimuli.mpg')

        """
        fileRoot, fileExt = os.path.splitext(fileName)
        if len(self.movieFrames) == 0:
            logging.error('no frames to write - did you forget to update '
                          'your window?')
            return
        else:
            logging.info('writing %i frames' % len(self.movieFrames))
        if fileExt == '.gif':
            makeMovies.makeAnimatedGIF(fileName, self.movieFrames)
        elif fileExt in ['.mpg', '.mpeg']:
            if sys.platform == 'darwin':
                raise IOError('Mpeg movies are not currently available under '
                              'OSX. You can use quicktime movies (.mov) '
                              'instead though.')
            makeMovies.makeMPEG(fileName, self.movieFrames, codec=mpgCodec)
        elif fileExt in ['.mov', '.MOV']:
            raise NotImplementedError("Support for Quicktime movies has been "
                                      "removed (at least for now). You need "
                                      "to export your frames as images "
                                      "(e.g. png files) and combine them "
                                      "yourself (e.g. with ffmpeg)")
        elif len(self.movieFrames) == 1:
            self.movieFrames[0].save(fileName)
        else:
            frame_name_format = "%s%%0%dd%s" % \
                (fileRoot,
                 numpy.ceil(numpy.log10(len(self.movieFrames) + 1)),
                 fileExt)
            for frameN, thisFrame in enumerate(self.movieFrames):
                thisFileName = frame_name_format % (frameN+1,)
                thisFrame.save(thisFileName)
        if clearFrames:
            self.movieFrames = []

    def _getRegionOfFrame(self, rect=[-1, 1, 1, -1],
                          buffer='front', power2=False, squarePower2=False):
        """
        Capture a rectangle (Left Top Right Bottom, norm units) of the window
        as an RBGA image.

        power2 can be useful with older OpenGL versions to avoid interpolation
        in PatchStim. If power2 or squarePower2, it will expand rect dimensions
        up to next power of two. squarePower2 uses the max dimenions. You need
        to check what your hardware & opengl supports, and call
        _getRegionOfFrame as appropriate.
        """
        # Ideally: rewrite using GL frame buffer object; glReadPixels == slow

        x, y = self.size  # of window, not image
        imType = 'RGBA'  # not tested with anything else

        # box corners in pix
        box = [(rect[0]/2. + 0.5)*x, (rect[1]/-2. + 0.5)*y,  # Left Top
               (rect[2]/2. + 0.5)*x, (rect[3]/-2. + 0.5)*y]  # Right Bottom
        box = map(int, box)

        horz = box[2] - box[0]
        vert = box[3] - box[1]

        if buffer == 'back':
            GL.glReadBuffer(GL.GL_BACK)
        else:
            GL.glReadBuffer(GL.GL_FRONT)

        #http://www.opengl.org/sdk/docs/man/xhtml/glGetTexImage.xml
        bufferDat = (GL.GLubyte * (4 * horz * vert))()
        GL.glReadPixels(box[0], box[1], horz, vert,
                        GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, bufferDat)
        # not right
        #GL.glGetTexImage(GL.GL_TEXTURE_1D, 0,
        #                 GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, bufferDat)
        im = Image.fromstring(mode='RGBA', size=(horz, vert), data=bufferDat)
        region = im.transpose(Image.FLIP_TOP_BOTTOM)

        if power2 or squarePower2:  # use to avoid interpolation in PatchStim
            if squarePower2:
                maxsize = max(region.size)
                xPowerOf2 = yPowerOf2 = int(2**numpy.ceil(numpy.log2(maxsize)))
            else:
                xPowerOf2 = int(2**numpy.ceil(numpy.log2(region.size[0])))
                yPowerOf2 = int(2**numpy.ceil(numpy.log2(region.size[1])))
            imP2 = Image.new(imType, (xPowerOf2, yPowerOf2))
            # paste centered
            imP2.paste(region, (int(xPowerOf2/2. - region.size[0]/2.),
                                int(yPowerOf2/2. - region.size[1]/2)))
            region = imP2

        return region

    def close(self):
        """Close the window (and reset the Bits++ if necess)."""
        if (not self.useNativeGamma) and self.origGammaRamp is not None:
            setGammaRamp(self.winHandle, self.origGammaRamp)
        self.setMouseVisible(True)
        if self.winType == 'pyglet':
            # If iohub is running, inform it to stop looking for this win id
            # when filtering kb and mouse events (if the filter is enabled of course)
            #
            if IOHUB_ACTIVE:
                from psychopy.iohub.client import ioHubConnection
                ioHubConnection.ACTIVE_CONNECTION.unregisterPygletWindowHandles(self._hw_handle)
            self.winHandle.close()
        else:
            #pygame.quit()
            pygame.display.quit()
        if self.bitsMode is not None:
            self.bits.reset()
        openWindows.remove(self)
        logging.flush()

    def fps(self):
        """Report the frames per second since the last call to this function
        (or since the window was created if this is first call)"""
        fps = self.frames/(self.frameClock.getTime())
        self.frameClock.reset()
        self.frames = 0
        return fps

    def setBlendMode(self, blendMode):
        self.blendMode = blendMode
        if blendMode=='avg':
            GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
            if hasattr(self, '_shaders'):
                self._progSignedTex = self._shaders['signedTex']
                self._progSignedTexMask = self._shaders['signedTexMask']
                self._progSignedTexMask1D = self._shaders['signedTexMask1D']
        elif blendMode=='add':
            GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)
            if hasattr(self, '_shaders'):
                self._progSignedTex = self._shaders['signedTex_adding']
                self._progSignedTexMask = self._shaders['signedTexMask_adding']
                self._progSignedTexMask1D = self._shaders['signedTexMask1D_adding']

    def setColor(self, color, colorSpace=None, operation=''):
        """Set the color of the window.

        NB This command sets the color that the blank screen will have on the
        next clear operation. As a result it effectively takes TWO `flip()`
        operations to become visible (the first uses the color to create the
        new screen, the second presents that screen to the viewer).

        See :ref:`colorspaces` for further information about the ways to
        specify colors and their various implications.

        :Parameters:

        color :
            Can be specified in one of many ways. If a string is given then it
            is interpreted as the name of the color. Any of the standard
            html/X11
            `color names <http://www.w3schools.com/html/html_colornames.asp>`
            can be used. e.g.::

                myStim.setColor('white')
                myStim.setColor('RoyalBlue')#(the case is actually ignored)

            A hex value can be provided, also formatted as with web colors.
            This can be provided as a string that begins with
            (not using python's usual 0x000000 format)::

                myStim.setColor('#DDA0DD')#DDA0DD is hexadecimal for plum

            You can also provide a triplet of values, which refer to the
            coordinates in one of the :ref:`colorspaces`. If no color space is
            specified then the color space most recently used for this
            stimulus is used again.

                # a red color in rgb space
                myStim.setColor([1.0,-1.0,-1.0], 'rgb')

                # DKL space with elev=0, azimuth=45
                myStim.setColor([0.0,45.0,1.0], 'dkl')

                # a blue stimulus using rgb255 space
                myStim.setColor([0,0,255], 'rgb255')

            Lastly, a single number can be provided, x,
            which is equivalent to providing [x,x,x].

                myStim.setColor(255, 'rgb255') #all guns o max

        colorSpace : string or None

            defining which of the :ref:`colorspaces` to use. For strings and
            hex values this is not needed. If None the default colorSpace for
            the stimulus is used (defined during initialisation).

        operation : one of '+','-','*','/', or '' for no operation
            (simply replace value)

            for colors specified as a triplet of values (or single intensity
            value) the new value will perform this operation on the previous
            color

                # increment all guns by 1 value
                thisStim.setColor([1,1,1],'rgb255','+')
                # multiply the color by -1 (which in this space inverts the
                # contrast)
                thisStim.setColor(-1, 'rgb', '*')
                # raise the elevation from the isoluminant plane by 10 deg
                thisStim.setColor([10,0,0], 'dkl', '+')
        """
        setColor(self, color, colorSpace=colorSpace, operation=operation,
                 rgbAttrib='rgb',  # or 'fillRGB' etc
                 colorAttrib='color')

        # these spaces are 0-centred
        if self.colorSpace in ['rgb', 'dkl', 'lms', 'hsv']:
            # RGB in range 0:1 and scaled for contrast
            desiredRGB = (self.rgb+1)/2.0
        else:
            desiredRGB = (self.rgb)/255.0

        # if it is None then this will be done during window setup
        if self.winHandle is not None:
            if self.winType == 'pyglet':
                self.winHandle.switch_to()
            GL.glClearColor(desiredRGB[0], desiredRGB[1], desiredRGB[2], 1.0)

    def setRGB(self, newRGB):
        """Deprecated: As of v1.61.00 please use `setColor()` instead
        """
        global GL, currWindow
        self.rgb = val2array(newRGB, False, length=3)
        if self.winType == 'pyglet' and currWindow != self:
            self.winHandle.switch_to()
        GL.glClearColor((self.rgb[0]+1.0)/2.0,
                        (self.rgb[1]+1.0)/2.0,
                        (self.rgb[2]+1.0)/2.0,
                        1.0)

    def _setupGamma(self):
        if self.gamma is not None:
            self._checkGamma()
            self.useNativeGamma = False
        elif self.monitor.getGamma() is not None:
            if hasattr(self.monitor.getGammaGrid(), 'dtype'):
                self.gamma = self.monitor.getGammaGrid()[1:, 2]
                # are we using the default gamma for all monitors?
                if self.monitor.gammaIsDefault():
                    self.useNativeGamma = True
                else:
                    self.useNativeGamma = False
            else:
                self.gamma = self.monitor.getGamma()
                self.useNativeGamma = False
        else:
            self.gamma = None  # gamma wasn't set anywhere
            self.useNativeGamma = True

        try:
            self.origGammaRamp = getGammaRamp(self.winHandle)
        except:
            self.origGammaRamp = None

        if self.useNativeGamma:
            if self.autoLog:
                logging.info('Using gamma table of operating system')
        else:
            if self.autoLog:
                logging.info('Using gamma: self.gamma' + str(self.gamma))
            self.setGamma(self.gamma)  # using either pygame or bits++

    def setGamma(self, gamma):
        """Set the monitor gamma, using Bits++ if possible"""

        self._checkGamma(gamma)

        if self.bitsMode is not None:
            #first ensure that window gamma is 1.0
            if self.winType == 'pygame':
                pygame.display.set_gamma(1.0, 1.0, 1.0)
            elif self.winType == 'pyglet':
                self.winHandle.setGamma(self.winHandle, 1.0)
            #then set bits++ to desired gamma
            self.bits.setGamma(self.gamma)
        elif self.winType == 'pygame':
            pygame.display.set_gamma(self.gamma[0],
                                     self.gamma[1],
                                     self.gamma[2])
        elif self.winType == 'pyglet':
            self.winHandle.setGamma(self.winHandle, self.gamma)

    def _checkGamma(self, gamma=None):
        if gamma is None:
            gamma = self.gamma
        if isinstance(gamma, (float, int)):
            self.gamma = [gamma]*3
        elif hasattr(gamma, '__iter__'):
            self.gamma = gamma
        else:
            raise ValueError('gamma must be a numeric scalar or iterable')

    def setScale(self, units, font='dummyFont', prevScale=(1.0, 1.0)):
        """DEPRECATED: this method used to be used to switch between units for
        stimulus drawing but this is now handled by the stimuli themselves and
        the window should aways be left in units of 'pix'
        """
        if units == "norm":
            thisScale = numpy.array([1.0, 1.0])
        elif units == "height":
            thisScale = numpy.array([2.0*self.size[1]/self.size[0], 2.0])
        elif units in ["pix", "pixels"]:
            thisScale = 2.0/numpy.array(self.size)
        elif units == "cm":
            #windowPerCM = windowPerPIX / CMperPIX
            #            = (window/winPIX) / (scrCm/scrPIX)
            if ((self.scrWidthCM in [0, None]) or
                    (self.scrWidthPIX in [0, None])):
                logging.error('you didnt give me the width of the screen '
                              '(pixels and cm). Check settings in '
                              'MonitorCentre.')
                core.wait(1.0)
                core.quit()
            thisScale = ((numpy.array([2.0, 2.0])/self.size) /
                         (float(self.scrWidthCM)/float(self.scrWidthPIX)))
        elif units in ["deg", "degs"]:
            #windowPerDeg = winPerCM*CMperDEG
            #               = winPerCM              * tan(pi/180) * distance
            if ((self.scrWidthCM in [0, None]) or
                    (self.scrWidthPIX in [0, None])):
                logging.error('you didnt give me the width of the screen '
                              '(pixels and cm). Check settings in '
                              'MonitorCentre.')
                core.wait(1.0)
                core.quit()
            cmScale = ((numpy.array([2.0, 2.0])/self.size) /
                       (float(self.scrWidthCM)/float(self.scrWidthPIX)))
            thisScale = cmScale * 0.017455 * self.scrDistCM
        elif units == "stroke_font":
            thisScale = numpy.array([2*font.letterWidth, 2*font.letterWidth] /
                                    self.size/38.0)
        #actually set the scale as appropriate
        # allows undoing of a previous scaling procedure
        thisScale = thisScale/numpy.asarray(prevScale)
        GL.glScalef(thisScale[0], thisScale[1], 1.0)
        return thisScale  # just in case the user wants to know?!

    def _checkMatchingSizes(self, requested, actual):
        """Checks whether the requested and actual screen sizes differ. If not
        then a warning is output and the window size is set to actual
        """
        if list(requested) != list(actual):
            logging.warning("User requested fullscreen with size %s, "
                            "but screen is actually %s. Using actual size" %
                            (requested, actual))
            self.size = numpy.array(actual)

    def _setupPyglet(self):
        self.winType = "pyglet"
        if self.allowStencil:
            stencil_size = 8
        else:
            stencil_size = 0
        # options that the user might want
        config = GL.Config(depth_size=8, double_buffer=True,
                           stencil_size=stencil_size, stereo=self.stereo)
        allScrs = \
            pyglet.window.get_platform().get_default_display().get_screens()
        # Screen (from Exp Settings) is 1-indexed,
        # so the second screen is Screen 1
        if len(allScrs) < int(self.screen) + 1:
            logging.warn("Requested an unavailable screen number - "
                         "using first available.")
            thisScreen = allScrs[0]
        else:
            thisScreen = allScrs[self.screen]
            if self.autoLog:
                logging.info('configured pyglet screen %i' % self.screen)
        #if fullscreen check screen size
        if self._isFullScr:
            self._checkMatchingSizes(self.size, [thisScreen.width,
                                                 thisScreen.height])
            w = h = None
        else:
            w, h = self.size
        if self.allowGUI:
            style = None
        else:
            style = 'borderless'
        self.winHandle = pyglet.window.Window(width=w, height=h,
                                              caption="PsychoPy",
                                              fullscreen=self._isFullScr,
                                              config=config,
                                              screen=thisScreen,
                                              style=style)
        if sys.platform =='win32':
            self._hw_handle=self.winHandle._hwnd
        elif sys.platform =='darwin':
            self._hw_handle=self.winHandle._window.value
        elif sys.platform =='linux2':
            self._hw_handle=self.winHandle._window

        #provide warning if stereo buffers are requested but unavailable
        if self.stereo and not GL.gl_info.have_extension('GL_STEREO'):
            logging.warning('A stereo window was requested but the graphics '
                            'card does not appear to support GL_STEREO')

        if self.useFBO and not GL.gl_info.have_extension('GL_EXT_framebuffer_object'):
            logging.warn("Trying to use a framebuffer pbject but GL_EXT_framebuffer_object is not supported. Disabling")
            self.useFBO=False
        #add these methods to the pyglet window
        self.winHandle.setGamma = setGamma
        self.winHandle.setGammaRamp = setGammaRamp
        self.winHandle.getGammaRamp = getGammaRamp
        self.winHandle.set_vsync(True)
        self.winHandle.on_text = event._onPygletText
        self.winHandle.on_key_press = event._onPygletKey
        self.winHandle.on_mouse_press = event._onPygletMousePress
        self.winHandle.on_mouse_release = event._onPygletMouseRelease
        self.winHandle.on_mouse_scroll = event._onPygletMouseWheel
        if not self.allowGUI:
            # make mouse invisible. Could go further and make it 'exclusive'
            # (but need to alter x,y handling then)
            self.winHandle.set_mouse_visible(False)
        self.winHandle.on_resize = self.onResize
        if not self.pos:
            # work out where the centre should be
            self.pos = [(thisScreen.width-self.size[0])/2,
                        (thisScreen.height-self.size[1])/2]
        if not self._isFullScr:
            # add the necessary amount for second screen
            self.winHandle.set_location(self.pos[0]+thisScreen.x,
                                        self.pos[1]+thisScreen.y)

        try:  # to load an icon for the window
            iconFile = os.path.join(psychopy.prefs.paths['resources'],
                                    'psychopy.ico')
            icon = pyglet.image.load(filename=iconFile)
            self.winHandle.set_icon(icon)
        except:
            pass  # doesn't matter

        # Code to allow iohub to know id of any psychopy windows created
        # so kb and mouse event filtering by window id can be supported.
        #
        # If an iohubConnection is active, give this window os handle to
        # to the ioHub server. If windows were already created before the
        # iohub was active, also send them to iohub.
        #
        if IOHUB_ACTIVE:
            from psychopy.iohub.client import ioHubConnection
            if ioHubConnection.ACTIVE_CONNECTION:
                winhwnds=[]
                for w in openWindows:
                    winhwnds.append(w._hw_handle)
                if self._hw_handle not in winhwnds:
                    winhwnds.append(self._hw_handle)
                ioHubConnection.ACTIVE_CONNECTION.registerPygletWindowHandles(*winhwnds)

    def _setupPygame(self):
        #we have to do an explicit import of pyglet.gl from pyglet
        # (only when using pygame backend)
        #Not clear why it's needed but otherwise drawing is corrupt. Using a
        #pyglet Window presumably gets around the problem
        import pyglet.gl as GL

        self.winType = "pygame"
        # pygame.mixer.pre_init(22050,16,2)#set the values to initialise
        # sound system if it gets used
        pygame.init()
        if self.allowStencil:
            pygame.display.gl_set_attribute(pygame.locals.GL_STENCIL_SIZE, 8)

        try:  # to load an icon for the window
            iconFile = os.path.join(psychopy.__path__[0], 'psychopy.png')
            icon = pygame.image.load(iconFile)
            pygame.display.set_icon(icon)
        except:
            pass  # doesn't matter

        # these are ints stored in pygame.locals
        winSettings = pygame.OPENGL | pygame.DOUBLEBUF
        if self._isFullScr:
            winSettings = winSettings | pygame.FULLSCREEN
            #check screen size if full screen
            scrInfo = pygame.display.Info()
            self._checkMatchingSizes(self.size, [scrInfo.current_w,
                                                 scrInfo.current_h])
        elif not self.pos:
            #centre video
            os.environ['SDL_VIDEO_CENTERED'] = "1"
        else:
            os.environ['SDL_VIDEO_WINDOW_POS'] = '%i,%i' % (self.pos[0],
                                                            self.pos[1])
        if sys.platform == 'win32':
            os.environ['SDL_VIDEODRIVER'] = 'windib'
        if not self.allowGUI:
            winSettings = winSettings | pygame.NOFRAME
            self.setMouseVisible(False)
            pygame.display.set_caption('PsychoPy (NB use with allowGUI=False '
                                       'when running properly)')
        else:
            self.setMouseVisible(True)
            pygame.display.set_caption('PsychoPy')
        self.winHandle = pygame.display.set_mode(self.size.astype('i'),
                                                 winSettings)
        pygame.display.set_gamma(1.0)  # this will be set appropriately later

    def _setupGL(self):
        if self.winType == 'pygame':
            try:
                pygame
            except:
                logging.warning('Requested pygame backend but pygame ,'
                                'is not installed or not fully working')
                self.winType = 'pyglet'

        #setup the context
        if self.winType == "pygame":
            self._setupPygame()
        elif self.winType == "pyglet":
            self._setupPyglet()

        #check whether shaders are supported
        # also will need to check for ARB_float extension,
        # but that should be done after context is created
        self._haveShaders = (self.winType == 'pyglet' and
                             pyglet.gl.gl_info.get_version() >= '2.0')

        #setup screen color
        #these spaces are 0-centred
        if self.colorSpace in ['rgb', 'dkl', 'lms', 'hsv']:
            #RGB in range 0:1 and scaled for contrast
            desiredRGB = (self.rgb+1)/2.0
        else:
            desiredRGB = self.rgb/255.0
        GL.glClearColor(desiredRGB[0], desiredRGB[1], desiredRGB[2], 1.0)
        GL.glClearDepth(1.0)

        GL.glViewport(0, 0, int(self.size[0]), int(self.size[1]))

        GL.glMatrixMode(GL.GL_PROJECTION)  # Reset The Projection Matrix
        GL.glLoadIdentity()
        GL.gluOrtho2D(-1, 1, -1, 1)

        GL.glMatrixMode(GL.GL_MODELVIEW)  # Reset The Projection Matrix
        GL.glLoadIdentity()

        GL.glDisable(GL.GL_DEPTH_TEST)
        #GL.glEnable(GL.GL_DEPTH_TEST)  # Enables Depth Testing
        #GL.glDepthFunc(GL.GL_LESS)  # The Type Of Depth Test To Do
        GL.glEnable(GL.GL_BLEND)

        GL.glShadeModel(GL.GL_SMOOTH)  # Color Shading (FLAT or SMOOTH)
        GL.glEnable(GL.GL_POINT_SMOOTH)

        #check for GL_ARB_texture_float
        # (which is needed for shaders to be useful)
        #this needs to be done AFTER the context has been created
        if not GL.gl_info.have_extension('GL_ARB_texture_float'):
            self._haveShaders = False

        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        #identify gfx card vendor
        self.glVendor = GL.gl_info.get_vendor().lower()

        if sys.platform == 'darwin':
            platform_specific.syncSwapBuffers(1)

        if self.useFBO:
            self._setupFrameBuffer()

        if self._haveShaders: #do this after setting up FrameBufferObject
            self._setupShaders()

    def _setupShaders(self):
        self._progSignedTexFont = _shaders.compileProgram(_shaders.vertSimple, _shaders.fragSignedColorTexFont)
        self._progFBOtoFrame = _shaders.compileProgram(_shaders.vertSimple, _shaders.fragFBOtoFrame)
        self._shaders = {}
        self._shaders['signedTex'] = _shaders.compileProgram(_shaders.vertSimple, _shaders.fragSignedColorTex)
        self._shaders['signedTexMask'] = _shaders.compileProgram(_shaders.vertSimple, _shaders.fragSignedColorTexMask)
        self._shaders['signedTexMask1D'] = _shaders.compileProgram(_shaders.vertSimple, _shaders.fragSignedColorTexMask1D)
        self._shaders['signedTex_adding'] = _shaders.compileProgram(_shaders.vertSimple, _shaders.fragSignedColorTex_adding)
        self._shaders['signedTexMask_adding'] = _shaders.compileProgram(_shaders.vertSimple, _shaders.fragSignedColorTexMask_adding)
        self._shaders['signedTexMask1D_adding'] = _shaders.compileProgram(_shaders.vertSimple, _shaders.fragSignedColorTexMask1D_adding)

    def _setupFrameBuffer(self):
        # Setup framebuffer
        self.frameBuffer = GL.GLuint()
        GL.glGenFramebuffersEXT(1, ctypes.byref(self.frameBuffer))
        GL.glBindFramebufferEXT(GL.GL_FRAMEBUFFER_EXT, self.frameBuffer)

        # Create texture to render to
        self.frameTexture = GL.GLuint()
        GL.glGenTextures(1, ctypes.byref(self.frameTexture))
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.frameTexture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D,
                           GL.GL_TEXTURE_MAG_FILTER,
                           GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D,
                           GL.GL_TEXTURE_MIN_FILTER,
                           GL.GL_LINEAR)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA32F_ARB,
                        int(self.size[0]), int(self.size[1]), 0,
                        GL.GL_RGBA, GL.GL_FLOAT, None)

        #attach texture to the frame buffer
        GL.glFramebufferTexture2DEXT(GL.GL_FRAMEBUFFER_EXT,
                                     GL.GL_COLOR_ATTACHMENT0_EXT,
                                     GL.GL_TEXTURE_2D, self.frameTexture, 0)

        status = GL.glCheckFramebufferStatusEXT (GL.GL_FRAMEBUFFER_EXT);
        if status != GL.GL_FRAMEBUFFER_COMPLETE_EXT:
            print "Error in framebuffer activation"
            return
        status = GL.glCheckFramebufferStatusEXT(GL.GL_FRAMEBUFFER_EXT)
        if status != GL.GL_FRAMEBUFFER_COMPLETE_EXT:
            logging.error("Error in framebuffer activation")
            return
        GL.glDisable(GL.GL_TEXTURE_2D)
        #clear the buffer (otherwise the texture memory can contain junk)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

    def setMouseVisible(self, visibility):
        """Sets the visibility of the mouse cursor.

        If Window was initilised with noGUI=True then the mouse is initially
        set to invisible, otherwise it will initially be visible.

        Usage:
            ``setMouseVisible(False)``
            ``setMouseVisible(True)``
        """
        if self.winType == 'pygame':
            wasVisible = pygame.mouse.set_visible(visibility)
        elif self.winType == 'pyglet':
            self.winHandle.set_mouse_visible(visibility)
        self.mouseVisible = visibility

    def getActualFrameRate(self, nIdentical=10, nMaxFrames=100,
                           nWarmUpFrames=10, threshold=1):
        """Measures the actual fps for the screen.

        This is done by waiting (for a max of nMaxFrames) until [nIdentical]
        frames in a row have identical frame times
        (std dev below [threshold] ms).

        If there is no such sequence of identical frames a warning is logged
        and `None` will be returned.

        :parameters:
            nIdentical:
                the number of consecutive frames that will be evaluated.
                Higher --> greater precision. Lower --> faster.

            nMaxFrames:
                the maxmimum number of frames to wait for a matching set of
                nIdentical

            nWarmUpFrames:
                the number of frames to display before starting the test
                (this is in place to allow the system to settle after opening
                the `Window` for the first time.

            threshold:
                the threshold for the std deviation (in ms) before the set
                are considered a match

        """
        if nIdentical > nMaxFrames:
            raise ValueError('nIdentical must be equal to or '
                             'less than nMaxFrames')
        recordFrmIntsOrig = self.recordFrameIntervals
        #run warm-ups
        self.setRecordFrameIntervals(False)
        for frameN in range(nWarmUpFrames):
            self.flip()
        #run test frames
        self.setRecordFrameIntervals(True)
        for frameN in range(nMaxFrames):
            self.flip()
            if (len(self.frameIntervals) >= nIdentical and
                    (numpy.std(self.frameIntervals[-nIdentical:]) <
                     (threshold/1000.0))):
                rate = 1.0/numpy.mean(self.frameIntervals[-nIdentical:])
                if self.screen is None:
                    scrStr = ""
                else:
                    scrStr = " (%i)" % self.screen
                if self.autoLog:
                    logging.debug('Screen%s actual frame rate measured at %.2f' %
                              (scrStr, rate))
                self.setRecordFrameIntervals(recordFrmIntsOrig)
                self.frameIntervals = []
                return rate
        #if we got here we reached end of maxFrames with no consistent value
        logging.warning("Couldn't measure a consistent frame rate.\n"
                        "  - Is your graphics card set to sync to "
                        "vertical blank?\n"
                        "  - Are you running other processes on your "
                        "computer?\n")
        return None

    def getMsPerFrame(self, nFrames=60, showVisual=False, msg='', msDelay=0.):
        """Assesses the monitor refresh rate (average, median, SD) under
        current conditions, over at least 60 frames.

        Records time for each refresh (frame) for n frames (at least 60),
        while displaying an optional visual. The visual is just eye-candy to
        show that something is happening when assessing many frames. You can
        also give it text to display instead of a visual,
        e.g., msg='(testing refresh rate...)'; setting msg implies
        showVisual == False.

        To simulate refresh rate under cpu load, you can specify a time to wait
        within the loop prior to doing the win.flip(). If 0 < msDelay < 100,
        wait for that long in ms.

        Returns timing stats (in ms) of:
        - average time per frame, for all frames
        - standard deviation of all frames
        - median, as the average of 12 frame times around the median
          (~monitor refresh rate)

        :Author:
            - 2010 written by Jeremy Gray
        """

        # lower bound of 60 samples--need enough to estimate the SD
        nFrames = max(60, nFrames)
        num2avg = 12  # how many to average from around the median
        if len(msg):
            showVisual = False
            showText = True
            myMsg = TextStim(self, text=msg, italic=True,
                             color=(.7, .6, .5), colorSpace='rgb', height=0.1, autoLog=False)
        else:
            showText = False
        if showVisual:
            x, y = self.size
            myStim = GratingStim(self, tex='sin', mask='gauss',
                                 size=[.6*y/float(x), .6], sf=3.0, opacity=.2,
                                 autoLog=False)
        clockt = []  # clock times
        # end of drawing time, in clock time units,
        # for testing how long myStim.draw() takes
        drawt = []

        if msDelay > 0 and msDelay < 100:
            doWait = True
            delayTime = msDelay/1000.  # sec
        else:
            doWait = False

        winUnitsSaved = self.units
        # norm is required for the visual (or text) display, as coded below
        self.units = 'norm'

        # accumulate secs per frame (and time-to-draw) for a bunch of frames:
        rush(True)
        for i in range(5):  # wake everybody up
            self.flip()
        for i in range(nFrames):  # ... and go for real this time
            clockt.append(core.getTime())
            if showVisual:
                myStim.setPhase(1.0/nFrames, '+', log=False)
                myStim.setSF(3./nFrames, '+', log=False)
                myStim.setOri(12./nFrames, '+', log=False)
                myStim.setOpacity(.9/nFrames, '+', log=False)
                myStim.draw()
            elif showText:
                myMsg.draw()
            if doWait:
                core.wait(delayTime)
            drawt.append(core.getTime())
            self.flip()
        rush(False)

        self.units = winUnitsSaved  # restore

        frameTimes = [(clockt[i] - clockt[i-1]) for i in range(1, len(clockt))]
        drawTimes = [(drawt[i] - clockt[i]) for
                     i in range(len(clockt))]  # == drawing only
        freeTimes = [frameTimes[i] - drawTimes[i] for
                     i in range(len(frameTimes))]  # == unused time

        # cast to float so that the resulting type == type(0.123)
        # for median
        frameTimes.sort()
        # median-most slice
        msPFmed = 1000. * float(numpy.average(
            frameTimes[(nFrames-num2avg)/2:(nFrames+num2avg)/2]))
        msPFavg = 1000. * float(numpy.average(frameTimes))
        msPFstd = 1000. * float(numpy.std(frameTimes))
        msdrawAvg = 1000. * float(numpy.average(drawTimes))
        msdrawSD = 1000. * float(numpy.std(drawTimes))
        msfree = 1000. * float(numpy.average(freeTimes))

        return msPFavg, msPFstd, msPFmed  # msdrawAvg, msdrawSD, msfree


def getMsPerFrame(myWin, nFrames=60, showVisual=False, msg='', msDelay=0.):
    """
    Deprecated: please use the getMsPerFrame method in the
    `psychopy.visual.Window` class.

    Assesses the monitor refresh rate (average, median, SD) under current
    conditions, over at least 60 frames.

    Records time for each refresh (frame) for n frames (at least 60), while
    displaying an optional visual. The visual is just eye-candy to show that
    something is happening when assessing many frames. You can also give it
    text to display instead of a visual, e.g., msg='(testing refresh rate...)';
    setting msg implies showVisual == False. To simulate refresh rate under
    cpu load, you can specify a time to wait within the loop prior to
    doing the win.flip(). If 0 < msDelay < 100, wait for that long in ms.

    Returns timing stats (in ms) of:
    - average time per frame, for all frames
    - standard deviation of all frames
    - median, as the average of 12 frame times around the median
      (~monitor refresh rate)

    :Author:
        - 2010 written by Jeremy Gray
    """
    return myWin.getMsPerFrame(nFrames=60, showVisual=showVisual, msg='',
                               msDelay=0.)
