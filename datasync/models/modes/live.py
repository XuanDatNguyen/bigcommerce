import requests

from datasync.libs.authorization import Authorization
from datasync.libs.prodict import Prodict
from datasync.libs.response import Response
from datasync.libs.utils import to_str, get_config_ini, json_decode, get_current_time, json_encode
from datasync.models.mode import ModelMode


class ModelModesLive(ModelMode):
	def __init__(self):
		super().__init__()
		self._last_status = 200


	def is_channel_exist(self, channel_type, identifier):
		params = {
			'type': channel_type,
			'identifier': identifier,
			'user_id': self._user_id,
			'limit': 1
		}
		channel = self.api('channels/private', params, 'get')
		if not channel or not channel.get('data'):
			return False
		channel_data = channel['data'][0]
		if not channel_data['deleted_at']:
			return True
		return channel_data


	def is_channel_name_exist(self, channel_name):
		params = {
			'name': channel_name,
			'user_id': self._user_id,
			'limit': 1
		}
		channel = self.api('channels/', params, 'get')
		return True if channel else False


	def create_channel(self, channel_id_exist = None):
		channel_data = self.get_channel_create_data()
		channel_id = None
		if channel_id_exist:
			channel_id = channel_id_exist
			channel_data['deleted_at'] = None
			self.api('channels/private/{}'.format(to_str(channel_id_exist)), channel_data, 'put')
			channel = self.api('channels/private/{}'.format(to_str(channel_id_exist)), method = 'get')
		else:
			channel = self.api('channels/private', channel_data, 'post')
			if not channel or self._last_status == 400:
				return Response().error()
			channel_id = channel['id']
		return Response().success(channel)


	def update_channel(self, channel_id, **kwargs):
		return self.api(f'channels/private/{channel_id}', kwargs, 'put')


	def delete_channel(self, channel_id):
		return self.api('channels/private/{}'.format(channel_id), method = 'delete')


	def create_product_sync_process(self, state_id, channel_id_exist = None, **kwargs):
		process_data = self.get_process_create_data(state_id)
		if kwargs:
			process_data.update(kwargs)
		process_id = None
		if channel_id_exist:
			process = self.api('processes', {'channel_id': channel_id_exist, 'type': 'product'}, 'get')
			if process and process.get('data'):
				process_data = process['data'][0]
				process_id = process_data['id']
		if not process_id:
			process = self.api('processes', process_data, 'post')
			if not process:
				return Response().error()
			process_id = process['id']
		return Response().success(process_id)


	def create_refresh_process_scheduler(self, channel_id):
		enable = self.api(f'channels/{channel_id}/enable-refresh', method = 'post')
		return Response().success()

	def create_order_sync_process(self, state_id, channel_id):
		process_data = self.get_process_create_data(state_id, 'order')
		process_id = None
		process = self.api('processes', {'channel_id': channel_id, 'type': 'order'}, 'get')
		if process and process.get('data'):
			process_data = process['data'][0]
			process_id = process_data['id']
		if process_id:
			self.api(f"processes/{process_id}", {'state_id': state_id, 'status': 'new'}, 'put')
			return process_id
		else:
			process = self.api(f"processes", process_data, 'post')
			if not process:
				return False
			return process['id']


	def create_inventory_sync_process(self, state_id, channel_id):
		process_data = self.get_process_create_data(state_id, 'inventory')
		process_id = None
		process = self.api('processes', {'channel_id': channel_id, 'type': 'inventory'}, 'get')
		if process and process.get('data'):
			process_data = process['data'][0]
			process_id = process_data['id']
		if process_id:
			self.api(f"processes/{process_id}", {'state_id': state_id, 'status': 'new'}, 'put')
			return process_id
		else:
			process = self.api(f"processes", process_data, 'post')
			if not process:
				return False
			return process['id']


	def delete_sync_process(self, sync_id):
		return self.api('processes/{}'.format(sync_id), method = 'delete')


	def get_sync_info(self, sync_id):
		sync = self.api('processes/{}'.format(to_str(sync_id)), method = 'get')
		if not sync:
			return sync
		return Prodict(**sync)


	def save_sync(self, sync_id, **kwargs):
		return self.api('processes/{}'.format(sync_id), kwargs, 'put')


	def get_all_channels(self):
		channels = self.api(f'channels', method = 'get')
		if not channels or channels.get('code') != 200:
			return False
		return list(map(lambda x: Prodict.from_dict(x), channels['data']))


	def api(self, path, data = None, method = 'post', time_out = None, merchant = False):
		api_url = get_config_ini('server', 'api_url').strip('/')
		if not merchant:
			api_url += '/api/'
		url = f"{api_url.strip('/')}/{to_str(path).strip('/')}"
		custom_header = self.get_custom_headers()
		res = self.request_by_method(method, url, data, custom_header, time_out = time_out)
		if method == 'delete':
			if self._last_status == 204:
				return Response().success()
			return Response().error()
		res_data = json_decode(res)
		if res_data is False or self._last_status >= 400:
			return False
		return res_data


	def get_custom_headers(self):
		user_id = to_str(self._user_id)
		custom_headers = dict()
		custom_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64;en; rv:5.0) Gecko/20110619 Firefox/5.0'
		custom_headers['Authorization'] = Authorization(private_key = get_config_ini('server', 'private_key'), user_id = user_id).encode()
		custom_headers['Content-Type'] = 'application/json'
		return custom_headers


	def request_by_method(self, method, url, data, custom_headers = None, auth = None, time_out = None):
		response_data = False
		response = None
		try:
			request_option = {
				'headers': custom_headers,
			}
			if data:
				if method in ['put', 'post']:
					request_option['json'] = data
				if method == 'get':
					request_option['params'] = data
			if not time_out:
				request_option['timeout'] = 180
			response = requests.request(method = method, url = url, **request_option)
			response_data = response.text
			self._last_status = response.status_code
			response.raise_for_status()
		except requests.exceptions.HTTPError as errh:
			msg = 'Url ' + url
			# msg += '\n Retry 5 times'
			msg += '\n Method: ' + method
			msg += '\n Status: ' + to_str(response.status_code) if response else ''
			msg += '\n Data: ' + to_str(data)
			msg += '\n Header: ' + to_str(response.headers)
			msg += '\n Response: ' + to_str(response_data)
			msg += '\n Error: ' + to_str(errh)
			self.log(msg, 'live')
		except requests.exceptions.ConnectionError as errc:
			self.log("Error Connecting:" + to_str(errc) + " : " + to_str(response_data))
		except requests.exceptions.Timeout as errt:
			pass
		except requests.exceptions.RequestException as err:
			self.log("OOps: Something Else" + to_str(err) + " : " + to_str(response_data))
		return response_data


	def get_entity_limit(self):
		return dict()


	def get_warehouse_locations(self):
		locations = self.api('warehouses', method = 'get')
		if locations and locations.get('data'):
			return locations['data']
		return []


	def get_warehouse_location_default(self):
		location = self.api('warehouses', data = {"default": 1}, method = 'get')
		if location and location.get('data'):
			return location['data'][0]['id']
		return 0


	def get_warehouse_location_fba(self):
		location = self.api('warehouses/fba', method = 'get')
		if location and location.get('data'):
			return location['data'][0]['id']
		return 0


	def get_process_file(self):
		channel = self.api('channels/private', data = {'type': 'file'}, method = 'get')
		if not channel or channel['code'] != 200 or not channel['data']:
			return channel
		channel_data = channel['data'][0]
		process = self.api('processes', data = {'channel_id': channel_data['id']}, method = 'get')
		if not process or process['code'] != 200 or not process['data']:
			return process

		return Prodict(**channel_data), Prodict(**process['data'][0])


	def set_state_id_for_sync(self, sync_id, state_id):
		return self.api('processes/{}'.format(sync_id), {'state_id': state_id}, method = 'put')


	def get_process_by_type(self, channel_id, process_type):
		process = self.api('processes', data = {'channel_id': channel_id, 'type': process_type}, method = 'get')
		if not process or process['code'] != 200 or not process['data']:
			return False
		return Prodict(**process['data'][0])


	def get_scheduler_info(self, scheduler_id):
		return self.api('scheduler/{}'.format(scheduler_id), method = 'get')


	def get_process_by_id(self, process_id):
		return self.api('processes/{}'.format(process_id), method = 'get')


	def create_scheduler_process(self, process_id):
		return self.api('scheduler/create/{}'.format(process_id), method = 'post')


	def set_last_time_scheduler(self, scheduler_id):
		data = {
			'last_time': get_current_time()
		}
		return self.api('scheduler/{}'.format(scheduler_id), data, method = 'put')


	def get_user_plan(self):
		return self.api('subscription/me', method = 'get')


	def try_upgrade_plan(self):
		return self.api('subscription/me/upgrade', method = 'post')


	def get_channel_default(self):
		params = {
			'default': 1,
			'user_id': self._user_id,
			'limit': 1
		}
		channel = self.api('channels/private', params, 'get')
		if not channel or not channel.get('data'):
			return False
		return channel['data'][0]


	def get_channel_by_id(self, channel_id):
		channel = self.api(f'channels/private/{channel_id}', method = 'get')
		if not channel:
			return False
		return Prodict.from_dict(channel)


	def get_user_info(self):
		user = self.api(f'accounts/me', method = 'get')
		if not user:
			return False
		return user


	def get_category_path(self, channel_type, type_search, params):
		data_category = self.api(f'merchant/{channel_type}/{type_search}', data = params, method = 'get', merchant = True)
		if not data_category:
			return False
		return data_category


	def after_import(self, channel_id, process_id):
		self.api(f'channels/private/{channel_id}/{process_id}/after-import', method = 'post')
