import os
import sys
import traceback

from datasync.libs.errors import Errors
from datasync.libs.response import Response
from datasync.libs.utils import log, to_str, json_encode, get_current_time, to_int, get_model
from datasync.models.channel import ModelChannel


class Controller:
    def __init__(self, data=None):
        self._response = Response()
        self._user_id = data.get('user_id') if data else None
        self._date_requested = get_current_time()
        self._order_channels = dict()
        self._product_channels = dict()
        self._data = data

    def response(self, res):
        if hasattr(res, 'to_json'):
            res = getattr(res, 'to_json')()
        if isinstance(res, (list, dict)):
            res = json_encode(res)
        print(res, end='')
        sys.exit(1)

    def execute(self, action, data=None):
        try:
            if hasattr(self, action):
                res = getattr(self, action)(data)
            else:
                res = Response().error(Errors.ACTION_INVALID)
        except Exception:
            # prefix = ""
            # if data:
            # 	if data.get('user_id'):
            # 		prefix = "user/" + to_str(data['user_id'])
            # 	if data.get("sync_id"):
            # 		prefix = os.path.join('processes', to_str(data['sync_id']))
            error = traceback.format_exc()
            # log(error, prefix_path = prefix)
            self.log(error)
            res = Response().error(Errors.EXCEPTION)
        if hasattr(res, 'code') and res.code and not res.msg:
            res.msg = Errors().get_msg_error(res.code)
        self.response(res)

    def log(self, msg, type_log='exceptions'):
        prefix = os.path.join("user", to_str(self._user_id))
        log(msg, prefix, type_log)

    def log_traceback(self, type_error='exceptions', entity_id=None):
        error = traceback.format_exc()
        if entity_id:
            error = type_error + ' ' + to_str(entity_id) + ': ' + error
        self.log(error, type_error)

    def get_channel_order(self, channel_id):
        """

        @rtype: ModelChannel
        """

        channel_id = to_int(channel_id)
        if not channel_id:
            return False
        if self._order_channels.get(channel_id):
            return self._order_channels[channel_id]
        bridge = ModelChannel()
        bridge.set_user_id(self._user_id)
        bridge.set_data(self._data)
        channel_data = bridge.get_channel_by_id(channel_id)
        if not channel_data:
            return False
        process = bridge.get_process_by_type(
            ModelChannel.PROCESS_TYPE_ORDER, channel_id)
        if not process:
            return False
        state = bridge.get_state_by_id(process['state_id'])
        if not state:
            return False
        channel = self.get_channel_by_state(state, process['id'])
        self._order_channels[channel_id] = channel
        return self._order_channels[channel_id]

    def get_channel_product(self, channel_id):
        """

        @rtype: ModelChannel
        """

        channel_id = to_int(channel_id)
        if not channel_id:
            return False
        if self._product_channels.get(channel_id):
            return self._product_channels[channel_id]
        bridge = ModelChannel()
        bridge.set_user_id(self._user_id)
        bridge.set_data(self._data)
        channel_data = bridge.get_channel_by_id(channel_id)
        if not channel_data:
            return False
        process = bridge.get_process_by_type(
            ModelChannel.PROCESS_TYPE_PRODUCT, channel_id)
        if not process:
            return False
        state = bridge.get_state_by_id(process['state_id'])
        if not state:
            return False
        channel = self.get_channel_by_state(state, process['id'])
        self._product_channels[channel_id] = channel
        return self._product_channels[channel_id]

    def get_channel_by_state(self, state=None, sync_id=None):
        channel_type = state.channel.channel_type
        channel_version = state.channel.config.version
        bridge = ModelChannel()
        bridge.set_user_id(self._user_id)
        channel_name, channel_class = bridge.get_channel(
            channel_type, channel_version)
        if not channel_name:
            channel = ModelChannel()
        else:
            channel = get_model(channel_name, class_name=channel_class)
        if not channel:
            return None
        channel.set_state(state)
        channel.set_sync_id(sync_id)
        channel.set_state_id(state._id)
        channel.set_db(bridge.get_db())
        channel.set_user_id(self._user_id)
        channel.set_data(self._data)
        if state.channel.name:
            channel.set_name(state.channel.name)
        if state.channel.id:
            channel.set_id(state.channel.id)
        if state.channel.identifier:
            channel.set_identifier(state.channel.identifier)
        if state.channel.url:
            channel.set_channel_url(state.channel.url)
        if state.channel.channel_type:
            channel.set_channel_type(state.channel.channel_type)
        return channel
