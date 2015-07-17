# CloudWatchLogs Logging
# Copyright 2015 Immobilien Scout GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from time import sleep
import logging
import logging.handlers
from threading import Timer, Lock

import boto.logs
from boto.exception import JSONResponseError
from boto.logs.exceptions import (DataAlreadyAcceptedException,
                                  InvalidSequenceTokenException,
                                  ResourceAlreadyExistsException)




class CloudWatchLogsHandler(logging.handlers.BufferingHandler):
    """
    Logging Handler writing to the AWS CloudWatch Logs Service, directly

    Needed Information:
        region (e.g. "eu-central-1")
        log_group_name
        log_stream_name

    Dependencies:
        boto: python library for the AWS API, see
            http://docs.pythonboto.org/en/latest/getting_started.html#installing-boto
        boto credentials, see
            http://docs.pythonboto.org/en/latest/getting_started.html#configuring-boto-credentials)

    Typical Usage:
        from cloudwatchlogs_logger import CloudWatchLogsHandler
        cwl_handler = CloudWatchLogsHandler(AWS_REGION, GROUP_NAME, STREAM_NAME)

        logger = logging.getLogger(LOGGER_NAME)
        logger.addHandler(cloudwatch_handler)
        logger.warn("Tadahhh")
    """

    MAX_BATCH_BYTES = 32768

    drop_fields = set(["threadName", "thread", "process", "processName",
                       "args", "lineno", "asctime", "relativeCreated", "msecs",
                       "exc_info", "levelno"])



    def __init__(self, region, log_group_name, log_stream_name,
                 flush_interval=60, capacity=1000, flush_level=logging.ERROR,
                 retries=10):
        assert capacity <= 10000, "max batch size is 10000"
        super(CloudWatchLogsHandler, self).__init__(capacity=capacity)
        self.region = region
        self.log_group_name = log_group_name
        self.log_stream_name = log_stream_name
        self.flush_interval = flush_interval
        self.flush_level = flush_level
        self.retries = retries
        self.connection = None
        self.sequence_token = None
        self.timer = None
        self._timer_lock = Lock()

    def create_group_and_stream(self, log_group_name, log_stream_name):
        try:
            self.connection.create_log_group(log_group_name)
        except ResourceAlreadyExistsException:
            pass
        try:
            self.connection.create_log_stream(log_group_name, log_stream_name)
        except ResourceAlreadyExistsException:
            pass

    def _lazy_connect(self):
        if self.connection:
            return
        self.connection = boto.logs.connect_to_region(self.region)
        self.create_group_and_stream(self.log_group_name, self.log_stream_name)

    def _put_events(self, events):
        self._lazy_connect()

        result = self.connection.put_log_events(
            self.log_group_name,
            self.log_stream_name,
            events,
            self.sequence_token)
        self.sequence_token = result.get("nextSequenceToken")

    def put_events(self, events):
        for _ in xrange(self.retries):
            try:
                return self._put_events(events)
            except (DataAlreadyAcceptedException, InvalidSequenceTokenException) as exc:
                if exc.status != 400:
                    raise
                next_sequence_token = exc.body.get("expectedSequenceToken")
                if next_sequence_token:
                    self.sequence_token = next_sequence_token
                else:
                    raise
            except JSONResponseError, e:
                if e.error_code == u'ThrottlingException':
                    sleep(1)
                else:
                    raise



    def _transform_record(self, record):
        timestamp = int(record.created * 1000)
        record_dict = {k:v for k,v in vars(record).iteritems() if v and k not in self.drop_fields}
        message = json.dumps(record_dict)
        event = {"message": message, "timestamp": timestamp}
        return event


    def emit(self, record):
        if not self.timer:
            self._start_timer()
        super(CloudWatchLogsHandler, self).emit(record)


    def flush(self):
        #TODO: add guarantees around number of events in buffer
        #TODO: ensure we do not go over batch byte size. split batches if necessary.
        with self._timer_lock:
            if self.timer:
                self.timer.cancel()
            self.timer = None
        if not self.buffer:
            return self._start_timer()

        records = self.buffer
        self.buffer = []
        records = map(self._transform_record, records)

        self.acquire()
        try:
            self.put_events(records)
        finally:
            self.release()

        self._start_timer()


    def _start_timer(self):
        with self._timer_lock:
            if not self.timer:
                self.timer = Timer(self.flush_interval, self.flush)
                self.timer.daemon = True
                self.timer.start()


    @staticmethod
    def _size(msg):
        return len(msg["message"]) + 26


    def shouldFlush(self, record):
        """
        Check for buffer full or a record at the flushLevel or higher.
        """
        #sum(map(self._size, self.buffer))
        #TODO: determine if it is time to flush based on how close we are to maximum buffer byte size
        return (len(self.buffer) >= self.capacity) or \
                (record.levelno >= self.flush_level)


