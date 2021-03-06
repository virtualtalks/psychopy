# -*- coding: utf-8 -*-
"""
Created on Mon Feb 10 17:13:14 2014

@author: zaheer
"""

import logging
import gevent, time
from collections import OrderedDict
from gevent import sleep, socket, queue
from gevent.server import StreamServer
from win32api import GetSystemMetrics
import json
from timeit import default_timer as getTime
from weakref import proxy

logging.basicConfig(filename='output.log',level=logging.DEBUG)
start = time.time()
tic = lambda: 'at %1.1f seconds' % (time.time() - start)    

class TheEyeTribe(object):
    """
    TheEyeTribe class is the client side interface to the TheEyeTribe 
    eye tracking device server.
    """
    sleepInterval = 0.1    
    sw = GetSystemMetrics(0)
    sh = GetSystemMetrics(1)
    calibrationPoints = 9 

    # define the dict format for tracker set msgs
    set_tracker_prototype = {
        "category": 'tracker',
        "request": 'set',
        "values": {}
        }
        
    # define the dict format for tracker get msgs
    get_tracker_prototype = {
        "category": 'tracker',
        "request": 'get',
        "values": []
        }

    # see http://dev.theeyetribe.com/api/#cat_tracker
    # list of valid get keys. If a get msg is sent that includes 
    # a key not in this list, that key value pair is ignored and not sent.
    tracker_get_values = [
        'push',
        'heartbeatinterval',
        'version',
        'trackerstate',
        'framerate',
        'iscalibrated',
        'iscalibrating',
        'calibresult',
        'frame',
        'screenindex',
        'screenresw',
        'screenresh',
        'screenpsyw',
        'screenpsyh'
    ]

    # list of valid set keys. If a set msg is sent that includes 
    # a key not in this list, that key value pair is ignored and not sent.
    tracker_set_values = [
        'push',
        'version',
        'screenindex',
        'screenresw',
        'screenresh',
        'screenpsyw',
        'screenpsyh'
    ]

    tracker_calibration_values = [
        'start',        
        'pointstart',
        'pointend',
        'clear'
    ]
    # tracker status states
    TRACKER_CONNECTED = 0 # Tracker device is detected and working
    TRACKER_NOT_CONNECTED = 1 #	Tracker device is not detected
    TRACKER_CONNECTED_BADFW = 2 # Tracker device is detected but not working due to wrong/unsupported firmware
    TRACKER_CONNECTED_NOUSB3 = 3 # Tracker device is detected but not working due to unsupported USB host
    TRACKER_CONNECTED_NOSTREAM = 4 # Tracker device is detected but not working due to no stream could be received

    # Tracker sample (frame) states

    # Tracker is calibrated and producing on-screen gaze coordinates.
    # Eye control is enabled.
    STATE_TRACKING_GAZE	= 0x1 # true: ((state & mask) != 0)
                              # false: ((state & mask) == 0)

    # Tracker possibly calibrated and is tracking both eyes,
    # including pupil and glint.
    STATE_TRACKING_EYES = 0x2 # true: ((state & mask) != 0)
                              # false: ((state & mask) == 0)

    # Tracker possibly calibrated and is tracking presence of user.
    # Presence defined as face or single eye.
    STATE_TRACKING_PRESENCE = 0x4 # true: ((state & mask) != 0)
                                  # false: ((state & mask) == 0)

    # Tracker failed to track anything in this frame.
    STATE_TRACKING_FAIL = 0x8 # true: ((state & mask) != 0)
                              # false: ((state & mask) == 0)
    # Tracker has failed to detect anything and tracking is now lost.
    STATE_TRACKING_LOST = 0x10 # true: ((state & mask) != 0)
                               # false: ((state & mask) == 0)

    def __init__(self):
        """
        When an instance of TheEyeTribe client interface is createdm,
        it creates two greenlets, a EyeTribeTransportManager and a 
        HeartbeatPump.
        """
        # _tracker_state is used to hold the last value received from the
        # eye tracker server for any tracker get keys sent. So as info
        # is requested from the server, the _tracker_state will hold a
        # up to date representation of any eye tracker server values returned
        # by the server based on get requests from the client.
        self._tracker_state={}
        
        self._transport_manager = EyeTribeTransportManager(self)
        self._transport_manager.start()
        
        self.sendSetMessage(push=True, version=1)
        self.sendGetMessage('push', 'version', 'screenresw', 'screenresh')

        self._heartbeat = HeartbeatPump(self._transport_manager)
        self._heartbeat.start()
        
        self.sendGetMessage(*self.tracker_get_values)
        
        self.calibrate()        

        
    @property
    def tracker_status(self):
        self.sendGetMessage('trackerstate')
        return self._tracker_state.get('trackerstate','Unknown')   
        
    @property
    def serverResponseCount(self):
        return self._transport_manager.server_response_count
        
    @property
    def tracker_state(self):
        return self._tracker_state
        
    def sendCalibrationMessage(self, request_type, **kwargs):
        """
        Examples:
            sendCalibrationMessage('start', pts=9)
            sendCalibrationMessage('pointstart',x=500,y=200)
            sendCalibrationMessage('pointend')
        """
        # TODO How to handle getting calibration response values from tracker
        
        if request_type not in self.tracker_calibration_values:
            # Throw error, return error code??
            print 'Unknown calibration request_type:',request_type
            return False
            
        calreq=OrderedDict(category='calibration', request = request_type)
        if kwargs:
            calreq['values'] = OrderedDict(sorted(kwargs.items(), key = lambda t:t[0]))
        send_str=json.dumps(calreq)
        print send_str
        logging.info(send_str)
        self._transport_manager.send(send_str)
        
        
    def calibrate(self):
        """
        Runs complete calibration process according to the TheEyeTribe APIs
        """
        self.sendCalibrationMessage('clear')
        gevent.sleep(self.sleepInterval)        
        self.sendCalibrationMessage('start', pointcount=self.calibrationPoints)
        gevent.sleep(self.sleepInterval)        
        sx_pos= [self.sw*0.25,self.sw*0.5,self.sw*0.75]
        sy_pos= [self.sh*0.25,self.sh*0.5,self.sh*0.75]

        for lx in sx_pos:
            for ly in sy_pos:
                self.sendCalibrationMessage('pointstart', x = int(lx), y = int(ly))
                gevent.sleep(self.sleepInterval)        
                self.sendCalibrationMessage('pointend')
            #gevent.sleep(self.sleepInterval)
        
    def sendSetMessage(self, **kwargs):
        """
        Send a Set Tracker msg to the server. any kwargs passed into this method
        are used as the key : value pairs that want to be sent to the server.
        
        For example:
        
        eyetracker.sendSetMessage(screenresw=1920,screenresh=1080) 
        
        would send a msg informing the tracker what the client's display 
        resolution is.        
        """
        send_values={}
        for k, v in kwargs.iteritems():
            if k not in self.tracker_set_values:
                print 'setTrackerMsg warning": Invalid tracker set value key \
                    [{0}] with value [{1}]. Ignoring'.format(k, v)
            else:
                send_values[k] = v

        self.set_tracker_prototype['values']=send_values
        send_str=json.dumps(self.set_tracker_prototype)
        self._transport_manager.send(send_str)
        self.set_tracker_prototype['values'] = None

    def sendGetMessage(self, *args):
        """
        Send a Get Tracker msg to the server. any args passed into this method
        are used as the keys that are to be sent to the server so the current
        value of each can be returned.
        
        For example:
        
        eyetracker.sendGetMessage('trackerstate','framerate') 
        
        would send a msg asking for the current eye tracker state and 
        framerate.
        """
        send_values=[]
        for k in args:
            if k not in self.tracker_get_values:
                print 'getTrackerMsg warning": Invalid tracker get value key \
                    [{0}]. Ignoring'.format(k)
            else:
                send_values.append(k)

        self.get_tracker_prototype['values'] = send_values
        send_str=json.dumps(self.get_tracker_prototype)
        self._transport_manager.send(send_str)
        self.get_tracker_prototype['values']=None

    def processSample(self,frame_dict):
        """
        Process an eye tracker sample frame that has been received.
        """
        #TODO proper handling of sample data
        sample_frame=frame_dict.get('values',{}).get('frame')
        print '!! Eye Sample Received:\n\tTime: {0}\n\tstate: {1}\n'.format(sample_frame['time'],sample_frame['state'])
        logging.info('!! Eye Sample Received:\n\tTime: {0}\n\tstate: {1}\n'.format(sample_frame['time'],sample_frame['state']))
        
    def processCalibrationResult(self, calibrationResult):
        """
        Process the calibration result
        """
        return True
        
    def close(self):
        """
        Close the eye tracker client by closing the transport_manager and
        heartbeat greenlets.
        """
        self._heartbeat.stop()
        self._transport_manager.stop()
        
#
########
#

class EyeTribeTransportManager(gevent.Greenlet):
    """
    EyeTribeTransportManager is used to handle tx and rx with the 
    eye tracker sever. This class is created by the TheEyeTribe class
    when an instance is created.
    
    The client_interface arg is the TheEyeTribe class instance that is
    creating the EyeTribeTransportManager.
    
    EyeTribeTransportManager creates a tcpip connection to the 
    eye tracker server which is used to send messages to the server
    as well as receive responses from the server.
    
    The HeartbeatPump and TheEyeTribe classes send msg's to the eye tracker
    server by calling EyeTribeTransportManager.send(msg_contents). The msg
    is added to the _tracker_requests_queue queue attribute.
    
    As the EyeTribeTransportManager class runs, it checks for any new msg's
    in the _tracker_requests_queue and sends any that are found to the server 
    via the _socket.
    
    As the EyeTribeTransportManager class runs, it is also checking for any 
    incoming data from the eye tracker server. If any is read, it is parsed into
    reply dict's. The type of server reply received is used to determine
    if it should be passed back to the HeartbeatPump or to the TheEyeTribe.
    """
    def __init__(self, client_interface):
        self.server_response_count=0
        self._client_interface=proxy(client_interface)
        gevent.Greenlet.__init__(self)
        self._tracker_requests_queue = queue.Queue()
        self._running = False
        self._socket = self.createConnection()
        
    def _run(self):
        self._running = True
        self.server_response_count=0
        msg_fragment=''
        while self._running:
            # used to know if the socket.sendall call timed out or not.
            tx_count=-1
            
            # Check for new messages to be sent to the server. 
            # Send them if found.
            try:
                to_send=self._tracker_requests_queue.get_nowait()
                tx_count=self._socket.sendall(to_send)
            except gevent.queue.Empty, e:
                pass
            except Exception, e:
                print 'MANAGER ERROR SENDING MSG:',e 
            #finally:
                # Yield to any other greenlets that are waiting to run.
                #gevent.sleep(0.0)
            
            # if a message was sent over the socket to the server, check
            # to see if any msg replies have been received from the server.
            reply=None
            try:
#                print 'rx looped'
                reply=self._socket.recv(512)
#                print 'rx recv done'
                if reply:
                    # The dummy server sometimes sends >1 server response
                    # in a single packet; to work around this the server
                    # puts '\r\n' at the end of each json string reply.
                    # This can then be used to split the text received 
                    # here into the correct number of msg json strs that
                    # should be converted to dict objects for processing.
                    # THE '\r\n' HACK SHOULD NOT BE NEEDED WHEN TALKING 
                    # TO THE REAL EYETRIBE SERVER.
                    #
#                    print 'org reply:', '%r'%(reply)
                    multiple_msgs=reply.split('\n')
                    multiple_msgs=[m for m in multiple_msgs if len(m)>0]
#                        print 'multiple_msgs:',len(multiple_msgs)
                    for m in multiple_msgs:
                        m='%s%s'%(msg_fragment,m)
                        try:
                            mdict=json.loads(m)
                            #print 'handleServerMsg:',mdict
                            self.handleServerMsg(mdict)
                            msg_fragment=''
                            self.server_response_count += 1
                        except:
                            msg_fragment=m
            except socket.timeout:
                pass#print 'socket.timeout'
            except socket.error, e:
                if e.errno==10035:
                    pass#print 'socket.error10035',e
                else:
                    #print ' socket.error: ',e
                    raise e
            except Exception, e:    
                print 'MANAGER ERROR RECEIVING REPLY MSG:',e
                print '>>>>>>>>>>>>'
                print type(e),dir(e)
                print  '%r'%(reply)
                if reply:  
                    print type(reply), len(reply)
                print '<<<<<<<<<<<<'
            finally:
                # Yield to any other greenlets that are waiting to run.
                gevent.sleep(0.001)
        
        # Greenlet has stopped running so close socket.
        self._running=False
        self._socket.close()

    def send(self,msg):
        """
        send is called by other classes that want to send a msg to the 
        eye tracker server. the msg is put in a queue that is emptied 
        as the EyeTribeTransportManager runs.
        """
        if not isinstance(msg,basestring):
            msg=json.dumps(msg)
        self._tracker_requests_queue.put(msg)
        
    def handleServerMsg(self,msg):
        msg_category=msg.get('category')
        msg_statuscode=msg.get('statuscode')
        if msg_statuscode != 200:
            if msg_statuscode == 802:
                # get updated eye tracker values
                self._client_interface.sendGetMessage(*self._client_interface.tracker_get_values)
            else:
                    
                # TODO Handle msg status code error values
                print '========'
                print 'SERVER REPLY ERROR:',msg_statuscode
                print msg
                print 'Server Msg not being processed due to error.'
                print '========'
                return False
            
        if msg_category == u'heartbeat':
            return True

        if msg_category == u'calibration':
            request_type=msg.get('request') 
            #print '::::::::::: Calibration Result: ', msg.get('values',{}).get('calibresult')            
            if request_type == u'pointend': 
                if msg.get('values',{}).get('calibresult'): 
                    print '::::::::::: Calibration Result: ', msg
                    logging.info('::::::::::: Calibration Result: {0}'.format(msg))                    
                    return self._client_interface.processCalibrationResult(msg)
                    return True

        if msg_category == u'calibration':
            request_type=msg.get('request') 
            if request_type == u'pointstart': 
                print '==========Calibration response: ', msg
                logging.info('==========Calibration response: {0}'.format(msg))
                return True
            if request_type == u'pointend': 
                print '+++++++++++ Calibration response: ', msg
                logging.info('+++++++++++ Calibration response: {0}'.format(msg))
                return True

        if msg_category == u'tracker':
            request_type=msg.get('request') 
            if request_type == u'get': 
                if msg.get('values',{}).get('frame'): 
                    return self._client_interface.processSample(msg)
                
                if msg.get('values',{}).get('screenresw') and msg.get('values',{}).get('screenresh'): 
                    self.sw = msg.get('values',{}).get('screenresw')
                    self.sh = msg.get('values',{}).get('screenresh')
                    #print 'Screen width: ', self.sw
                    #print 'Screen height: ', self.sh
                    return True
                print 'GET Rx received from server but unhandled.'
                # TODO : check statuscode field of get response for any errors
                # TODO : update theeyetribe classes .tracker_state dict with
                #        the key : value pairs in the values field.
                #        i.e. something like the following 3 commented out lines: 
                #
                # for k,v in msg.get('values',{}).iteritems():
                #    print '* Updating client.tracker_state[{0}] = {1}'.format(k,v)
                #    self._client_interface.tracker_state[k]=v
                return True
            if request_type == u'set': 
                print 'SET Rx received from server.'
                # TODO check status field for any errors
                return True        
        print '>> Warning: Unhandled Server packet category [{0}] received by client. Full msg contents:\n\n{1}\n<<'.format(msg_category,msg)                

    def createConnection(self, host='localhost', port=6555):
        # Open a socket to the eye tracker server
        try:
            hbp = socket.socket()
            hbp.connect((host, port))
            #print 'current timeout:',hbp.gettimeout()
            hbp.settimeout(0.01)
            #print 'current timeout2:',hbp.gettimeout()
            return hbp
        except Exception, e:
            print 'Error creating exception:',e
            return None

    def stop(self):
        self._socket.close()
#
########
#

class HeartbeatPump(gevent.Greenlet):
    """
    HeartbeatPump keeps theeyetribse sever alive.
    """
    
    get_heartbeat_rate={"category": "tracker", "request" : "get",
                        "values": [ "heartbeatinterval" ]
                        }
    heartbeat={ 'category' : 'heartbeat' }                    
    def __init__(self,transport_manager,sleep_interval=0.25):
        """
        HeartbeatPump is used by TheEyeTribe client class to keep the server
        running. 
        
        transport_manager the instance of the EyeTribeTransportManager created
        prior to creating the TheEyeTribe instance.
        
        sleep_interval is the time to delay between sending heartbeats
        
        HeartbeatPump will run until it is stopped.
        """
        gevent.Greenlet.__init__(self)
        self._transport_manager = transport_manager
        self._running = False
        self.sleep_interval = sleep_interval
        
        # Convert the class message dict constants to the associated json
        # strings that will actually be sent.
        #
        HeartbeatPump.get_heartbeat_rate=json.dumps(self.get_heartbeat_rate)
        HeartbeatPump.heartbeat=json.dumps(self.heartbeat)
    
    def getHeartbeatRate(self):
        '''
        request the rate the server is expecting to receive heartbeats at.
        '''
        self._transport_manager.send(self.get_heartbeat_rate)  

    def pump(self):
        """
        Send a heartbeat msg to the server.
        """
        #print 'HB Queued.'
        self._transport_manager.send(self.heartbeat)  
        
    def _run(self):
        self._running = True
        self.getHeartbeatRate() # get the heartbeet interval. TODO : use the
                                # val returned to override the default
                                # sleep_interval.
        while self._running:
            gevent.sleep(self.sleep_interval)
            self.pump()
            
    def stop(self):
        """
        Stops the Greenlet from sending heartbeat msg's.
        """
        self._running=False

#
##### MAIN SCRIPT
#

TEST_WITH_DUMMY_SERVER=False
        
if __name__ == '__main__':
    # run client connected to a very stupid fake server if the real one is
    # not available.
    if TEST_WITH_DUMMY_SERVER:
        from dummyserver import startDummyServer
        server = startDummyServer(('',6555))
    
    # create an instance of the client interface to theeyetribe eye tracker.
    tracker = TheEyeTribe()
   
    # in this silly example, just wait until 100 responses or sample frames 
    # have been received by the client.
    while tracker.serverResponseCount < 60:
        #print 'main app loop:',getTime()
        #tracker.calibrate()        
        sleep(1.00)
        
    

    # Close the tracker client interface.
    tracker.close()
    
    print 'End of Test!'