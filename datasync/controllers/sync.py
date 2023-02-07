import time

from datasync.controllers.channel import ControllerChannel, to_int
from datasync.libs.response import Response
from datasync.libs.utils import to_str


class ControllerSync(ControllerChannel):
	def __init__(self, data = None):
		super().__init__(data = None)


	def pull(self, data = None):
		current = self._state.sync.resume.type
		if not current:
			current = 'taxes'
		self.init()
		if not self._state:
			return Response().success()
		result = Response().process()
		self._state.sync.pull.resume.type = current
		if not self._state.config.get_attribute(current):
			next_action = self._pull_next_entity[current]
			result = self.next_entity_pull(current, next_action)
			self.save_pull_process(data)
			return result
		total = to_int(self._state.sync.pull.process[current].total)
		imported = to_int(self._state.sync.pull.process[current].imported)
		limit = to_int(self._state.sync.pull.process[current].limit)
		error = to_int(self._state.sync.pull.process[current].error)
		id_src = to_int(self._state.sync.pull.process[current].id_src)
		simple_action = self._import_simple_entity[current]
		next_action = self._pull_next_entity[current]
		if limit == -1 or imported < limit:
			fn_get_main = getattr(self.get_channel(), 'get_{}_main_export'.format(current))
			fn_get_ext = getattr(self.get_channel(), 'get_{}_ext_export'.format(current))
			fn_convert_export = getattr(self.get_channel(), 'convert_{}_export'.format(simple_action))
			add_channel_to_convert_data = getattr(self.get_channel(), 'add_channel_to_convert_{}_data'.format(simple_action))
			fn_get_id = getattr(self.get_channel(), 'get_{}_id_import'.format(simple_action))
			fn_check_import = getattr(self.get_warehouse(), 'check_{}_import'.format(simple_action))
			fn_before_import = getattr(self.get_warehouse(), 'before_{}_import'.format(simple_action))
			fn_import = getattr(self.get_warehouse(), '{}_import'.format(simple_action))
			fn_after_import = getattr(self.get_warehouse(), 'after_{}_import'.format(simple_action))
			fn_addition_import = getattr(self.get_warehouse(), 'addition_{}_import'.format(simple_action))
			log_times = list()
			try:
				start_time = time.time()
				mains = fn_get_main()

				if mains.result != Response().SUCCESS:
					if mains.result == Response().FINISH:
						result = self.next_entity_pull(current, next_action)
						return result
					if self._retry <= 10:
						time.sleep(self._retry * 10)
						self.log('get main error, sleep ' + to_str(self._retry * 10) + 's', 'mains')
						self._retry += 1
						return mains
					else:
						self._retry = 0
						return Response().create_response(result = Response.STOP_EXPORT)

				if not mains.data:
					if self._state.channel.setup_type == 'api':
						if self._retry >= 5:
							return Response().create_response(result = Response.STOP_EXPORT)

						self._retry += 1
						time.sleep(60)
						return Response().create_response(result = Response.PROCESS)

					else:
						result = self.next_entity_pull(current, next_action)
						return result
				if self._state.channel.setup_type == 'api':
					self._retry = 0
				ext = fn_get_ext(mains.data)
				log_times.append('request source ' + to_str(time.time() - start_time) + 's')
				if ext.result != Response().SUCCESS:
					self.log('get ext error', 'ext')
					return Response().create_response(result = Response.STOP_EXPORT)
			except Exception:
				self.log_traceback()
				if self._state.config.stop_on_error:
					return Response().create_response(Response.STOP)
				else:
					return Response().create_response(Response.STOP_EXPORT)
			ext_data = ext.data
			for main in mains.data:
				id_src = fn_get_id(None, main, ext_data)
				try:
					if limit != -1 and imported >= limit:
						break
					imported += 1
					start_time = time.time()
					convert = fn_convert_export(main, ext_data)
					if convert.resule in [Response.SKIP]:
						continue
					if convert.result == Response.ERROR:
						error += 1
						if not convert.msg:
							convert.msg = "convert " + to_str(id_src) + " error"
						self.log(convert['msg'], current + '_errors')
						if self._state.config.stop_on_error:
							return Response().create_response(Response.STOP)
						continue
					if convert.result == Response.WARNING:

						if not convert['msg']:
							convert['msg'] = "convert " + to_str(id_src) + " error"
						self.log(convert['msg'], current + '_warning')
						if self._state.config.stop_on_error:
							return Response().create_response(Response.STOP)
						continue
					convert_data = convert.data
					convert_data = add_channel_to_convert_data(convert_data, id_src)
					check_import = fn_check_import(id_src, convert_data)
					if check_import:
						continue
					import_data = fn_import(convert_data, main, ext_data)
					if import_data.result != Response.SUCCESS:
						msg = import_data.get('msg')
						if not msg:
							msg = "import " + to_str(id_src) + " error"
						self.log(msg, current + '_errors')

					if import_data.result == Response.SKIP_ERROR:
						error += 1
						continue

					if import_data.result == Response.error:
						error += 1
						if self._state.config.stop_on_error:
							return Response().create_response(Response.STOP)
						continue
					if import_data['result'] == 'warning':
						if self._state.config.stop_on_error:
							return Response().create_response(Response.STOP)

						error += 1
						continue
					id_desc = import_data.data
					after_import = fn_after_import(id_desc, convert_data, main, ext)
					if after_import.result == Response.ERROR:
						return after_import

					log_times.append(current + ' id ' + to_str(id_src) + ': ' + 'request target ' + to_str(time.time() - start_time) + 's')
				except Exception:
					self.log_traceback(current + '_errors', id_src)
					if self._state.config.stop_on_error:
						return Response().create_response(Response.STOP)
					error += 1
					continue

			self.log_time(log_times)
			self._state.sync.pull.process[current].imported = imported
			self._state.sync.pull.process[current].error = error
			self._state.sync.pull.process[current].id_src = id_src
		else:
			if hasattr(self.get_channel(), 'finish_' + simple_action + '_export'):
				try:
					getattr(self.get_channel(), 'finish_' + simple_action + '_export')()
					self._state = self.get_channel().get_state()
					self.get_warehouse().set_state(self._state)

				except Exception:
					self.log_traceback()
			if hasattr(self.get_warehouse(), 'finish_' + simple_action + '_import'):
				try:
					getattr(self.get_warehouse(), 'finish_' + simple_action + '_import')()
					self._state = self.get_warehouse().get_state()

				except Exception:
					self.log_traceback()
			result = self.next_entity_pull(current, next_action)
		if self.get_channel().get_action_stop() or self.get_warehouse().get_action_stop():
			return Response().create_response(Response.STOP_EXPORT)

		self.save_pull_process(data)
		return result
