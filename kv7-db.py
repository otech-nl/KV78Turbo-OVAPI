import sys
import zmq
import simplejson as serializer
import time
from ctx import ctx
from gzip import GzipFile
from cStringIO import StringIO
import psycopg2
import time
from datetime import datetime, timedelta
from const import ZMQ_KV7
from twisted.internet import task
from twisted.internet import reactor

conn = psycopg2.connect("dbname='kv78turbo' user='postgres'")

sys.stderr.write('Setting up a ZeroMQ PUSH: %s\n' % (ZMQ_KV7))
context = zmq.Context()
push = context.socket(zmq.PUSH)
push.connect(ZMQ_KV7)

def secondsFromMidnight(time):
	hours, minutes, seconds = time.split(':')
	return (int(hours)*60*60) + (int(minutes)*60) + int(seconds)
	
def time(seconds):
        hours = seconds / 3600
        if hours < 0:
                hours += 24
        seconds -= 3600*hours
        minutes = seconds / 60
        if minutes < 0:
                minutes *= -1
        seconds -= 60*minutes
        return "%02d:%02d:%02d" % (hours, minutes, seconds)
        
now = datetime.now() + timedelta(hours=1) - timedelta(seconds=60)

def fetchandpushkv7():
	passes = {}
	global now # this has to be done better
	now += timedelta(seconds=60)
	startrange = now.strftime("%H:%M:00")
	startdate = now.strftime("%Y-%m-%d")
	endrange = (now + timedelta(seconds=60)).strftime("%H:%M:00")
	if endrange == '00:00:00':
		endrange = '24:00:00'
	shours,sminutes,sseconds = startrange.split(':')
	ehours,eminutes,eseconds = endrange.split(':')
	startrange48 = str(int(shours)+24) + ':' + sminutes + ':00'
	endrange48 = str(int(ehours)+24) + ':' + eminutes + ':00'
	sys.stdout.write(startrange + '-' + endrange + '@ ' + startdate) 
	sys.stdout.write(' ')
	sys.stdout.write(startrange48 + '-' + endrange48 + '\n')
	cur = conn.cursor()
	cur.execute("SELECT p.dataownercode,p.localservicelevelcode,p.lineplanningnumber,journeynumber,fortifyordernumber,p.userstopcode,userstopordernumber,linedirection,p.destinationcode,targetarrivaltime,targetdeparturetime,sidecode,wheelchairaccessible,journeystoptype,istimingstop,productformulatype,destinationname50,timingpointcode, timingpointdataownercode,operationdate,linename,transporttype,linepublicnumber FROM localservicegrouppasstime  AS ""p"", destination AS ""d"", usertimingpoint as ""u"", localservicegroupvalidity as ""v"", line as ""l"" WHERE p.dataownercode = l.dataownercode AND p.lineplanningnumber = l.lineplanningnumber AND journeystoptype != 'INFOPOINT' AND p.dataownercode = u.dataownercode AND p.userstopcode =  u.userstopcode AND ((operationdate = date %s AND targetarrivaltime >= %s AND targetarrivaltime < %s) OR (operationdate = date %s - interval '1 day' AND targetarrivaltime >= %s AND targetarrivaltime < %s))  AND p.localservicelevelcode = v.localservicelevelcode AND p.dataownercode = v.dataownercode AND p.destinationcode = d.destinationcode;", [startdate, startrange,endrange,startdate,startrange48,endrange48])
	kv7rows = cur.fetchall()
	passes = {}
	print str(len(kv7rows)) + ' rows from db'
	for kv7row in kv7rows:
		row = {}
		row['DataOwnerCode'] = kv7row[0]
		row['LocalServiceLevelCode'] = str(kv7row[1])
		row['LinePlanningNumber'] = kv7row[2]
		row['JourneyNumber'] = str(kv7row[3])
		row['FortifyOrderNumber'] = str(kv7row[4])
		row['UserStopCode'] = kv7row[5]
		row['UserStopOrderNumber'] = str(kv7row[6])
		if str(kv7row[7]) == 'A':
			row['LineDirection'] = '1'
		elif str(kv7row[7]) == 'B':
			row['LineDirection'] = '2'
		else:
			row['LineDirection'] = str(kv7row[7])
		row['DestinationCode'] = kv7row[8]
		row['TargetArrivalTime'] = kv7row[9]
		row['ExpectedArrivalTime'] = kv7row[9]
		row['TargetDepartureTime'] = kv7row[10]
		row['ExpectedDepartureTime'] = kv7row[10]
		row['SideCode'] = kv7row[11]
		row['WheelChairAccessible'] = kv7row[12]
		row['JourneyStopType'] = kv7row[13]
		row['IsTimingStop'] = kv7row[14]
		row['ProductFormulaType'] = kv7row[15]
		row['DestinationName50'] = kv7row[16]
		row['TimingPointCode'] = kv7row[17]
		row['TimingPointDataOwnerCode'] = kv7row[18]
		row['OperationDate'] = kv7row[19].strftime("%Y-%m-%d")
		row['LineName'] = kv7row[20]
		row['TransportType'] = kv7row[21]
		row['LinePublicNumber'] = kv7row[22]
		row['TripStopStatus'] = 'PLANNED'
		pass_id = '_'.join([row['DataOwnerCode'], row['LocalServiceLevelCode'], row['LinePlanningNumber'], row['JourneyNumber'], row['FortifyOrderNumber'], row['UserStopCode'], row['UserStopOrderNumber']])
		passes[pass_id] = row
		if (len(passes) > 50):
			push.send_json(passes)
			passes = {}
	push.send_json(passes)

l = task.LoopingCall(fetchandpushkv7)
l.start(60.0) # call every second
reactor.run()