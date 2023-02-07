import copy

from datasync.controllers.controller import Controller
from datasync.libs.errors import Errors
from datasync.libs.response import Response
from datasync.libs.utils import *
from datasync.models.channel import ModelChannel
from datasync.models.constructs.order import Order
from datasync.models.constructs.product import Product
from datasync.models.constructs.state import StateChannelAuth, SyncState, EntityProcess
from datasync.models.warehouse import ModelWareHouse


class ControllerChannel(Controller):
    PULL_START_ACTION = 'display_pull'
    PULL_CART_START_ACTION = 'cart_display_pull'
    ACTION_UPDATE = 'update'
    _state: SyncState or None
    _bridge: ModelChannel or None
    _channel: ModelChannel or None
    _channel_default: ModelChannel or None
    _warehouse: ModelWareHouse or None
    _pull_next_action = {
        'display_pull': 'clear_pull',
        'clear_pull': 'prepare_pull',
        'prepare_pull': 'pull',
        'pull': 'finish_pull',
        'finish_pull': False,
        'cart_display_pull': 'cart_pull',
        'cart_pull': False,
        'cart_finish_pull': False
    }
    _pull_next_entity = {
        'taxes': 'categories',
        'categories': 'products',
        'products': 'orders',
        'orders': False,
    }
    _push_next_entity = {
        'taxes': 'categories',
        'categories': 'products',
        'products': 'orders',
        'orders': False,
    }
    _import_simple_entity = {
        'taxes': 'tax',
        'categories': 'category',
        'products': 'product',
        'orders': 'order',
    }
    _push_next_action = {
        'display_push': 'clear_push',
        'clear_push': 'prepare_push',
        'prepare_push': 'push',
        'push': 'finish_push',
        'finish_push': False
    }
    ACTION_PULL = 'pull'
    ACTION_PUSH = 'push'
    ALLOW_ACTION = (ACTION_PULL, ACTION_PUSH)

    def __init__(self, data=None):
        super().__init__(data)
        self._pid = os.getpid()
        self._update = False
        self._import = True
        self._template_update = False
        self._refresh = False
        self._product_id = data.get(
            'product_id') if isinstance(data, dict) else None
        self._process_type = data.get(
            'process_type') if isinstance(data, dict) else None
        self._retry = 0
        self._state = None
        self._refresh_all_product = False
        self._bridge = None
        self._channel = None
        self._channel_default = None
        self._warehouse = None
        self._publish_action = None
        self._is_push_action = data.get(
            'is_push_action') if isinstance(data, dict) else False
        self._test = data.get('test') if isinstance(data, dict) else False
        self._sync_id = data.get('sync_id') if isinstance(data, dict) else None
        self._channel_id = data.get(
            'channel_id') if isinstance(data, dict) else None
        self._state_id = None
        self._warehouse_action = data.get(
            'warehouse_action') if isinstance(data, dict) else None
        self._channel_action = data.get(
            'channel_action') if isinstance(data, dict) else None
        self._channel_get_main_action = data.get(
            '_channel_get_main_action') if isinstance(data, dict) else None
        self._user_id = data.get('user_id') if isinstance(data, dict) else None
        self._is_inventory_process = data.get(
            'inventory_process') if isinstance(data, dict) else None
        self._src_channel_id = data.get(
            'src_channel_id') if isinstance(data, dict) else None
        self._data = data

    def set_src_channel_id(self, channel_id):
        self._src_channel_id = channel_id

    def get_src_channel_id(self):
        return self._src_channel_id

    def log(self, msg, log_type='exceptions'):
        prefix = "user/" + to_str(self._user_id)
        if self._channel_id:
            prefix = os.path.join('channel', to_str(self._channel_id))
            if self._process_type:
                prefix += '/' + self._process_type
        elif self._sync_id:
            prefix = os.path.join('processes', to_str(self._sync_id))
        elif self._product_id:
            prefix = os.path.join(prefix, 'product', to_str(self._product_id))

        log(msg, prefix, log_type)

    def reset_channel(self):
        self._channel = None
        self.get_channel()

    def restart_pull(self, data=None):
        self.init()
        if self._state.pull.resume.process == ModelChannel.PROCESS_PULLING:
            return
        self._state.pull.resume.action = ''
        self._state.pull.resume.process = ModelChannel.PROCESS_PULLING
        if self._process_type == 'order':
            self._update = True
            self._state.pull.resume.type = 'orders'
        elif self._process_type == 'refresh':
            if not self.get_channel().is_run_refresh():
                return Response().success()
            self._channel_get_main_action = 'get_product_by_updated_at'
            self._refresh_all_product = True
            if self.get_channel().get_channel_type() != 'file':
                self._import = False
            self._update = True
            self._state.pull.resume.type = 'products'
        elif self._process_type == 'product':
            if self.get_channel().get_channel_type() == 'file':
                if self.get_channel().is_csv_update():
                    self._update = True
                    self._import = False
                if self.get_channel().is_csv_add_new():
                    self._update = True
                    self._import = True
            self._state.pull.resume.type = 'taxes'
            channel_default = self.get_channel_default()
            if channel_default.get_channel_type() == 'file':
                if not self._data.get('auto_import'):
                    self._data['auto_import'] = list()
                self._data['auto_import'].append(
                    channel_default.get_channel_id())
        elif self._process_type == 'inventory':
            self._state.pull.resume.type = 'products'
            self._channel_action = 'sync_inventory'
        elif self._process_type == 'category':
            self._state.pull.resume.type = 'taxes'

        return self.start_pull(data)

    def start_pull(self, data=None):
        self.log("Starting pull " + to_str(self._pid), 'process')
        self.init()
        self._state.finish = False
        self._state.running = True
        self._state.resume.action = self.ACTION_PULL
        update = {
            'finish': False,
            'running': True,
            'push.resume': self._state.push.resume,
            'resume.action': self.ACTION_PULL,
            'pid': self._pid,
            'server_id': get_server_id()
        }
        self.get_bridge().update_state(update)
        self.save_sync(status=ModelChannel.PROCESS_PULLING)
        action = self.get_action_pull()
        check_stop = to_int(self.is_stop_process())
        retry = 0
        while check_stop not in [FLAG_KILL_ALL, FLAG_STOP]:
            result = getattr(self, action)(data)
            if result['result'] in (Response.STOP, Response.STOP_EXPORT):
                self._state.pull.resume.process = ModelChannel.PROCESS_STOPPED
                self.save_sync(status=ModelChannel.PROCESS_STOPPED)
                break
            if result['result'] == 'success':
                if self._pull_next_action[action]:
                    retry = 0
                    action = self._pull_next_action[action]
                    self._state.pull.resume.action = action
                    self.save_pull_process(data)
                else:
                    break
            time.sleep(0.1)
            check_stop = to_int(self.is_stop_process())
        # if check_stop == FLAG_KILL_ALL:
        # 	self.save_sync()
        # elif check_stop == FLAG_STOP:
        # 	self.save_sync()
        # else:
        # 	self.save_sync()
        self.save_pull_process(data)
        self.log("Exiting pull " + to_str(self._pid), 'process')

    def get_action_pull(self):
        resume_process = self._state.pull.resume.action
        if resume_process:
            return resume_process
        return self.PULL_START_ACTION if self._state.channel.channel_type not in self.get_bridge().all_cart() else self.PULL_CART_START_ACTION

    def is_stop_process(self):
        return 0

    def log_time(self, log_times):
        file_log = os.path.join(get_pub_path(), 'log', to_str(
            self._sync_id), 'time_request.log')
        if os.path.isfile(file_log):
            os.remove(file_log)
        for log_time in log_times:
            self.log(log_time, 'time_requests')

    def save_pull_process(self, data=None):
        if not self._refresh:
            return self.get_bridge().save_pull_process(data)
        return True

    def save_push_process(self, data=None):
        return self.get_bridge().save_push_process(data)

    def setup(self, data):
        self.init()
        validate = self.get_bridge().validate_data_setup(data)

        if validate.result != Response.SUCCESS:
            return validate
        self._state = self.get_bridge().get_state()
        channel_type = data['channel_type']
        channel_setup_type = self.get_bridge().channel_setup_type(channel_type)

        # previous_state = copy.deepcopy(self._state)
        if self._sync_id:
            self._state = None
        self.init(True)
        self._state.channel.channel_type = channel_type
        self._state.channel.setup_type = channel_setup_type
        self._state.channel.config.token = data.get('token')
        self._state.channel.name = data['channel_name']
        channel_url = self.get_channel().format_url(data['channel_url'])
        self._state.channel.url = channel_url
        self.get_channel().set_channel_url(channel_url)
        if data.get('test'):
            self._state.config.test = data.get('test')
        if data.get('auth'):
            self._state.channel.config.auth.username = data['auth']['username']
            self._state.channel.config.auth.password = data['auth']['password']
        else:
            self._state.channel.config.auth = StateChannelAuth()

        self.get_bridge().set_state(self._state)
        self.get_channel().set_state(self._state)
        prepare_setup_channel = self.get_channel().prepare_display_setup_channel(data)
        self._state = self.get_channel().get_state()
        if prepare_setup_channel.result != Response.SUCCESS:
            return prepare_setup_channel
        display_setup_channel = self.get_channel().display_setup_channel(data)
        self._state = self.get_channel().get_state()
        if display_setup_channel.result != Response.SUCCESS:
            return display_setup_channel
        custom_data = display_setup_channel.data
        set_channel_identifier = self.get_channel().set_channel_identifier()
        self._state = self.get_channel().get_state()
        if set_channel_identifier.result != Response.SUCCESS:
            return set_channel_identifier
        self.reset_channel()
        if custom_data:
            self.get_channel().update_custom_data(custom_data)
        prepare_setup_warehouse = self.get_warehouse().prepare_display_setup_warehouse(data)
        self._state = self.get_channel().get_state()
        if prepare_setup_warehouse.result != Response.SUCCESS:
            return prepare_setup_warehouse
        display_setup_warehouse = self.get_warehouse().display_setup_warehouse(data)
        self._state = self.get_warehouse().get_state()
        if display_setup_warehouse.result != Response.SUCCESS:
            return display_setup_warehouse
        self.get_bridge().set_state(self._state)
        self.get_channel().set_state(self._state)
        channel = self.get_channel().create_channel()
        if channel.result != Response().SUCCESS:
            return channel
        self.set_state_id(channel.data.state_id)
        after_create = self.get_channel().after_create_channel(channel.data)
        if after_create.result != Response().SUCCESS:
            self.get_channel().delete_channel(channel.data.channel_id)
            self.get_channel().delete_sync_process(channel.data.process_id)
            return after_create
        # if self.get_channel().is_channel_default():
        # 	self.get_channel().create_refresh_process_scheduler()
        self._state = self.get_channel().get_state()
        self.save_state()
        return Response().success(channel.data)

    def verify_connection(self, data):
        validate = self.get_bridge().validate_data_setup(data)
        if validate.result != Response.SUCCESS:
            return validate
        self.init()
        identifier = self._state.channel.identifier
        display_setup_channel = self.get_channel().display_setup_channel(data)
        self._state = self.get_channel().get_state()
        if display_setup_channel.result != Response.SUCCESS:
            return display_setup_channel
        self.get_channel().set_channel_identifier()
        new_identifier = self.get_channel().get_identifier()
        if to_str(identifier).replace('www.', '') != to_str(new_identifier).replace('www.', ''):
            return Response().error(Errors.RECONNECT_DIFFERENT_SITE)

        self.save_state()
        return Response().success(self._state.channel.config.api)

    # TODO: PULL

    def display_pull(self, data=None):
        self.init()
        if not self.get_channel():
            return Response().error()
        prepare_display_pull = self.get_bridge().prepare_display_pull(data)
        if prepare_display_pull.result != Response().SUCCESS:
            return prepare_display_pull
        self._state = self.get_bridge().get_state()
        self.get_channel().set_state(self._state)
        display_pull_channel = self.get_channel().display_pull_channel()
        if display_pull_channel.result != Response().SUCCESS:
            return display_pull_channel
        self._state = self.get_channel().get_state()
        self.get_warehouse().set_state(self._state)
        display_pull_warehouse = self.get_warehouse().display_pull_warehouse()
        if display_pull_warehouse.result != Response().SUCCESS:
            return display_pull_warehouse
        self._state = self.get_warehouse().get_state()
        self.get_bridge().set_state(self._state)
        display_import = self.get_bridge().display_pull()
        if display_import.result != Response().SUCCESS:
            return display_import
        self._state = self.get_bridge().get_state()
        self.save_state()
        return Response().success()

    def clear_pull(self, data=None):
        return Response().success()

    # self.init()
    # if self._state['target']['clear']['result'] == 'success' or self._state['config'].get('recent') or self._state['config'].get('add_new'):
    # 	return response_success()
    # result = self.default_result_migration()
    # # cart = get_model('basecart')
    # # getattr(cart, 'set_migration_id')(self._migration_id)
    # # self.init_cart()
    # # target_cart = self.get_target_cart(cart)
    # if not self.get_target_cart():
    # 	result['result'] = 'success'
    # 	return result
    # clear_data = getattr(self.target_cart, 'clear_data')()
    # self._state = getattr(self.target_cart, 'get_state')()
    # if clear_data['result'] == 'success' and self._state['config']['taxes']:
    # 	self.source_cart = self.get_source_cart()
    # 	if not self.source_cart:
    # 		result['result'] = 'success'
    # 		return result
    # 	prepare_souce = getattr(self.source_cart, 'prepare_taxes_export')()
    # 	self._state = getattr(self.source_cart, 'get_state')()
    # 	getattr(self.get_target_cart(), 'set_state')(self._state)
    # 	prepare_target = getattr(self.target_cart, 'prepare_taxes_import')()
    # 	self._state = getattr(self.target_cart, 'get_state')()
    # 	self._state['process']['taxes']['time_start'] = time.time()
    #
    # 	self._state['resume']['type'] = 'taxes'
    #
    # save_state = self.save_state()
    # if not save_state:
    # 	return response_error()
    # return clear_data

    def prepare_pull(self, data=None):
        self.init()
        if not self.get_channel():
            return Response().error()
        prepare_pull_channel = self.get_channel().prepare_pull_channel(data)
        if prepare_pull_channel.result != Response().SUCCESS:
            return prepare_pull_channel
        self._state = self.get_channel().get_state()
        self.get_warehouse().set_state(self._state)
        prepare_pull_warehouse = self.get_warehouse().prepare_pull_warehouse()
        if prepare_pull_warehouse.result != Response().SUCCESS:
            return prepare_pull_warehouse
        self._state = self.get_warehouse().get_state()
        self.get_bridge().set_state(self._state)
        prepare_pull = self.get_bridge().prepare_pull()
        if prepare_pull.result != Response().SUCCESS:
            return prepare_pull
        self._state = self.get_bridge().get_state()
        self.save_state()
        return Response().success()

    def pull(self, data=None):
        current = self._state.pull.resume.type
        if not current:
            current = 'taxes'
        self.init()
        if not self._state:
            return Response().success()
        result = Response().process()
        self._state.pull.resume.type = current
        if not self._state.config.get_attribute(current):
            next_action = self._pull_next_entity[current]
            result = self.next_entity_pull(current, next_action)
            self.save_pull_process(data)
            return result
        total = to_int(
            self._state.pull.process[current].total) if not self._refresh else 1
        imported = to_int(
            self._state.pull.process[current].imported) if not self._refresh else 0
        new_entity = to_int(self._state.pull.process[current].new_entity)
        if not new_entity:
            new_entity = 0
        limit = to_int(self._state.pull.process[current].limit)
        error = to_int(self._state.pull.process[current].error)
        id_src = to_int(self._state.pull.process[current].id_src)
        simple_action = self._import_simple_entity[current]
        next_action = self._pull_next_entity[current]
        if (total == -1 or imported < total) and (not limit or imported < limit):
            if self._channel_get_main_action and hasattr(self.get_channel(), self._channel_get_main_action):
                fn_get_main = getattr(self.get_channel(),
                                      self._channel_get_main_action)
            else:
                fn_get_main = getattr(self.get_channel(),
                                      'get_{}_main_export'.format(current))
            fn_get_ext = getattr(self.get_channel(),
                                 'get_{}_ext_export'.format(current))
            fn_convert_export = getattr(
                self.get_channel(), 'convert_{}_export'.format(simple_action))
            add_channel_to_convert_data = getattr(
                self.get_channel(), 'add_channel_to_convert_{}_data'.format(simple_action))
            fn_get_id = getattr(self.get_channel(),
                                'get_{}_id_import'.format(simple_action))
            fn_check_import = getattr(
                self.get_warehouse(), 'check_{}_import'.format(simple_action))
            fn_before_import = getattr(
                self.get_warehouse(), 'before_{}_import'.format(simple_action))
            fn_import = getattr(self.get_warehouse(),
                                '{}_import'.format(simple_action))
            fn_after_import = getattr(
                self.get_warehouse(), 'after_{}_import'.format(simple_action))
            fn_channel_after_import = getattr(
                self.get_channel(), 'after_{}_pull'.format(simple_action))
            fn_addition_import = getattr(
                self.get_warehouse(), 'addition_{}_import'.format(simple_action))
            log_times = list()
            imported_pack = 0
            try:
                start_time = time.time()
                if not self._refresh:
                    mains = fn_get_main()
                else:
                    fn_get_product = getattr(
                        self.get_channel(), 'get_{}_main_export'.format(simple_action))
                    mains = fn_get_product(self._product_id)

                if mains.result != Response.SUCCESS:
                    if mains.result == Response.FINISH:
                        result = self.next_entity_pull(current, next_action)
                        return result
                    if self._retry <= 10:
                        time.sleep(self._retry * 10)
                        self.log('get main error, sleep ' +
                                 to_str(self._retry * 10) + 's', 'mains')
                        self._retry += 1
                        return mains
                    else:
                        self._retry = 0
                        return Response().create_response(result=Response.STOP_EXPORT)

                if not mains.data:
                    result = self.next_entity_pull(current, next_action)
                    return result
                if self._state.channel.setup_type == 'api':
                    self._retry = 0
                ext = fn_get_ext(mains.data)
                log_times.append('request source ' +
                                 to_str(time.time() - start_time) + 's')
                if ext.result != Response().SUCCESS:
                    self.log('get ext error', 'ext')
                    return Response().create_response(result=Response.STOP_EXPORT)
            except Exception:
                self.log_traceback()
                if self._state.config.stop_on_error:
                    return Response().create_response(Response.STOP)
                else:
                    return Response().create_response(Response.STOP_EXPORT)
            ext_data = ext.data
            for main in mains.data:
                if self.get_channel().is_refresh_process():
                    self.get_channel().set_product_max_last_modified(main)
                id_src = fn_get_id(None, main, ext_data)
                try:
                    if (imported + imported_pack >= total != -1) or (limit and imported + imported_pack >= limit):
                        break
                    imported_pack += 1
                    start_time = time.time()
                    if not id_src:
                        continue
                    check_import = fn_check_import(id_src, main)
                    if check_import:

                        if self._update and hasattr(self.get_warehouse(), '{}_update'.format(simple_action)):
                            convert = fn_convert_export(main, ext_data)
                            if convert.result in [Response.SKIP]:
                                continue
                            if convert.result == Response.ERROR:
                                error += 1
                                if not convert.msg:
                                    convert.msg = "convert " + \
                                        to_str(id_src) + " error"
                                self.log(convert['msg'], current + '_errors')
                                if self._state.config.stop_on_error:
                                    return Response().create_response(Response.STOP)
                                continue
                            if convert.result == Response.WARNING:

                                if not convert['msg']:
                                    convert['msg'] = "convert " + \
                                        to_str(id_src) + " error"
                                self.log(convert['msg'], current + '_warning')
                                if self._state.config.stop_on_error:
                                    return Response().create_response(Response.STOP)
                                continue
                            convert_data = convert.data
                            convert_data = add_channel_to_convert_data(
                                convert_data, id_src)
                            current_entity = getattr(
                                self.get_channel(), f"get_current_{simple_action}")(check_import)
                            getattr(self.get_warehouse(), '{}_update'.format(simple_action))(
                                check_import, convert_data, main, None, current_entity)
                            if hasattr(self, 'finish_{}_update'.format(simple_action)):
                                getattr(self, 'finish_{}_update'.format(simple_action))(
                                    check_import, id_src, convert_data, current_entity)
                        continue
                    if self._refresh or self._refresh_all_product or not self._import:
                        continue
                    new_entity += 1
                    convert = fn_convert_export(main, ext_data)
                    if convert.result in [Response.SKIP]:
                        continue
                    if convert.result == Response.ERROR:
                        error += 1
                        if not convert.msg:
                            convert.msg = "convert " + \
                                to_str(id_src) + " error"
                        self.log(convert['msg'], current + '_errors')
                        if self._state.config.stop_on_error:
                            return Response().create_response(Response.STOP)
                        continue
                    if convert.result == Response.WARNING:

                        if not convert['msg']:
                            convert['msg'] = "convert " + \
                                to_str(id_src) + " error"
                        self.log(convert['msg'], current + '_warning')
                        if self._state.config.stop_on_error:
                            return Response().create_response(Response.STOP)
                        continue
                    convert_data = convert.data
                    convert_data = add_channel_to_convert_data(
                        convert_data, id_src)

                    import_data = fn_import(convert_data, main, ext_data)
                    if import_data.result != Response.SUCCESS:
                        msg = import_data.get('msg')
                        if not msg:
                            msg = "import " + to_str(id_src) + " error"
                        self.log(msg, current + '_errors')
                    if import_data.result == Response.STOP:
                        return import_data
                    if import_data.result == Response.SKIP_ERROR:
                        error += 1
                        continue

                    if import_data.result == Response.ERROR:
                        error += 1
                        if self._state.config.stop_on_error:
                            return Response().create_response(Response.STOP)
                        continue
                    if import_data['result'] == 'warning':
                        if self._state.config.stop_on_error:
                            return Response().create_response(Response.STOP)

                        error += 1
                        continue
                    id_desc, entity_data = import_data.data
                    after_import = fn_after_import(
                        id_desc, convert_data, main, ext)
                    if after_import.result == Response.ERROR:
                        return after_import
                    after_channel_import = fn_channel_after_import(
                        id_desc, convert_data, main, ext)
                    if hasattr(self, 'finish_{}_import'.format(simple_action)):
                        getattr(self, 'finish_{}_import'.format(
                            simple_action))(id_desc, entity_data)

                    log_times.append(current + ' id ' + to_str(id_src) + ': ' +
                                     'request target ' + to_str(time.time() - start_time) + 's')
                except Exception as e:
                    self.log_traceback(current + '_errors', id_src)
                    if self._state.config.stop_on_error:
                        return Response().create_response(Response.STOP)
                    error += 1
                    continue

            self.log_time(log_times)
            self._state.pull.process[current].new_entity = new_entity

            self.get_channel().set_state(self._state)
            getattr(self.get_channel(), f"set_imported_{simple_action}")(
                imported_pack)
            self._state = self.get_channel().get_state()
            self._state.pull.process[current].error = error
            if hasattr(self.get_channel(), 'set_{}_id_src'.format(simple_action)):
                self.get_channel().set_state(self._state)
                getattr(self.get_channel(), 'set_{}_id_src'.format(
                    simple_action))(id_src)
                self._state = self.get_channel().get_state()
            else:
                self._state.pull.process[current].id_src = id_src
        else:

            result = self.next_entity_pull(current, next_action)
        if self.get_channel().get_action_stop() or self.get_warehouse().get_action_stop():
            return Response().create_response(Response.STOP_EXPORT)

        self.save_pull_process(data)
        return result

    def next_entity_pull(self, current, next_action):
        simple_action = self._import_simple_entity[current]

        self.init()
        if hasattr(self.get_channel(), 'finish_' + simple_action + '_export'):
            try:
                getattr(self.get_channel(), 'finish_' +
                        simple_action + '_export')()
                self._state = self.get_channel().get_state()
                self.get_warehouse().set_state(self._state)

            except Exception:
                self.log_traceback()
        if hasattr(self.get_warehouse(), 'finish_' + simple_action + '_import'):
            try:
                getattr(self.get_warehouse(), 'finish_' +
                        simple_action + '_import')()
                self._state = self.get_warehouse().get_state()

            except Exception:
                self.log_traceback()
        if hasattr(self, 'addition_' + simple_action + '_import'):
            try:
                getattr(self, 'addition_' + simple_action + '_import')()

            except Exception:
                self.log_traceback()
        result = Response().process()
        time_finish = time.time()
        self._state.pull.process[current].time_finish = to_int(time_finish)
        if next_action:
            if self._state.config.next_action:
                fn_prepare_source = 'prepare_' + next_action + '_export'
                fn_prepare_target = 'prepare_' + next_action + '_import'
                getattr(self.get_channel(), fn_prepare_source)()
                self._state = self.get_channel().get_state()
                self.get_warehouse().set_state(self._state)
                getattr(self.get_warehouse(), fn_prepare_target)()
                self._state = self.get_warehouse().get_state()
            self._state.pull.process[next_action].time_start = time.time()
            self._state.pull.process[next_action].time_finish = 0
            self._state.pull.resume.type = next_action
        else:
            result.result = 'success'
        return result

    def finish_pull(self, data=None):
        self.init()
        prepare_display_finish = self.get_bridge().prepare_display_finish_pull()
        if prepare_display_finish.result != Response.SUCCESS:
            return prepare_display_finish
        self._state = self.get_bridge().get_state()

        self.get_channel().set_state(self._state)
        display_finish_source = self.get_channel().display_finish_channel_pull()
        if display_finish_source.result != Response.SUCCESS:
            return display_finish_source
        self._state = self.get_channel().get_state()
        self.get_warehouse().set_state(self._state)
        display_finish_warehouse = self.get_warehouse().display_finish_pull_warehouse()
        if display_finish_warehouse.result != Response.SUCCESS:
            return display_finish_warehouse
        self._state = self.get_warehouse().get_state()
        self.get_bridge().set_state(self._state)
        display_finish = self.get_bridge().display_finish_pull()
        if display_finish.result != Response.SUCCESS:
            return display_finish
        # if self.get_channel().allow_scheduler_pull_order() and self._process_type == 'product' and not self._state.channel.create_order_process:
        # 	create = self.get_bridge().create_scheduler_process(self._state.channel.id)
        # 	if create:
        # 		self._state.channel.create_order_process = True
        # if self.get_channel().allow_scheduler_pull_product() and self._process_type == 'product' and not self._state.channel.create_sync_process:
        # 	create = self.get_bridge().create_inventory_process(self._state)
        # 	if create:
        # 		self._state.channel.create_sync_process = True
        self.save_sync(status=ModelChannel.PROCESS_COMPLETED)

        self._state = self.get_bridge().get_state()
        self._state.pull.resume.process = ModelChannel.PROCESS_COMPLETED
        self._state.running = False
        self._state.finish = True
        self.save_state()
        self.save_pull_process(data)
        return Response().success()

    def start_update(self, data=None):
        self._update = True
        self.set_publish_action(self.ACTION_UPDATE)
        self.init()
        self._state.resume.description = self.ACTION_UPDATE
        return self.restart_push(data)

    def start_sync(self, data=None):
        # self.set_publish_action(self.ACTION_UPDATE)
        self.init()
        self._state.push.process.products.previous_start_time = self._state.push.process.products.start_time
        self._state.push.process.products.start_time = time.time()
        self.get_channel().set_state(self._state)
        self.get_warehouse().set_state(self._state)
        self.get_bridge().set_state(self._state)
        if self.get_channel().is_inventory_process():
            self._channel_action = 'sync_inventory'
        return self.restart_push(data)

    def start_template_update(self, data=None):
        self._template_update = True
        self._update = True
        # self.set_publish_action(self.ACTION_UPDATE)
        self.init()
        # self._state.resume.description = self.ACTION_UPDATE
        return self.restart_push(data)

    def start_refresh_list_product(self, data=None):
        self._refresh = True
        self._update = True
        self.init()
        product_ids = data['product_ids']
        for product_id in product_ids:
            self.sync_product_from_channel(product_id)
        return Response().success()

    def sync_product_from_channel(self, product_id):
        try:
            main = self.get_channel().get_product_main_export(product_id)
            if main.result == Response.DELETED:
                delete_product = self.get_warehouse().product_deleted(product_id)
                return Response().create_response(result='deleted')

            if main.result != Response.SUCCESS:
                return Response().success()
            product = main.data
            ext = self.get_channel().get_products_ext_export([product])
            if ext.result != Response.SUCCESS:
                return Response().success()
            convert = self.get_channel().convert_product_export(product, ext.data)
            if convert.result != Response.SUCCESS:
                return Response().success()
            id_src = self.get_channel().get_product_id_import(None, product, ext.data)
            check_import = self.get_warehouse().check_product_import(id_src, convert.data)
            if not check_import:
                return Response().success()
            # convert_data = convert.data
            # convert_data = self.get_channel().add_channel_to_convert_product_data(convert_data, id_src)
            update = self.get_warehouse().product_update(
                product_id, convert.data, product, None)
        except:
            self.log_traceback()
        return Response().success()

    def start_refresh_product(self, data=None):
        self._refresh = True
        self._update = True
        self.init()
        return self.sync_product_from_channel(self._product_id)

    def sync_order(self, data=None):
        channel_default = self.get_channel_default()
        if not channel_default:
            return Response().success()
        order_id = data['order_id']
        self.set_sync_id(channel_default.get_sync_id())
        self.init()
        try:
            if not data.get('order'):
                main = self.get_channel().get_order_main_export(order_id)
                if main.result != Response.SUCCESS:
                    return Response().success()
                order = main.data
            else:
                order = data['order']
            order = Prodict.from_dict(order)

            ext = self.get_channel().get_orders_ext_export([order])
            if ext.result != Response.SUCCESS:
                return Response().success()
            id_src = self.get_channel().get_order_id_import(None, order, ext.data)
            check_import = self.get_warehouse().check_order_import(id_src, order)
            if not check_import:
                return Response().success()
            convert = self.get_channel().convert_order_export(order, ext.data)
            if convert.result != Response.SUCCESS:
                return Response().success()
            convert_order = self.get_warehouse().convert_order(convert.data, None, None)
            if not convert_order:
                return Response().success()
            current_order = self.get_warehouse().get_current_order(check_import)
            update = self.get_warehouse().sync_order_status(
                check_import, convert_order, copy.deepcopy(current_order))
            if update.result != Response.SUCCESS:
                return Response().success()
            self.finish_order_update(
                check_import, id_src, convert_order, copy.deepcopy(current_order))
            order_updated = update.data
            order_channel_id = order_updated.channel_id
            channel = self.get_channel_order(order_channel_id)
            if not channel:
                return Response().success()
            channel.update_order_to_channel(order_updated, current_order)
        except:
            self.log_traceback()
        return Response().success()

    def start_scheduler(self, data=None):
        self.init()
        if not self.get_channel().is_run_scheduler():
            return Response().success()
        if self._process_type == 'order':
            return self.start_pull_update(data)
        elif self._process_type == 'inventory':
            self._state.push.resume.type = 'products'
            if not self._state.channel.default:
                self._channel_action = 'sync_inventory'
                return self.restart_push(data)
        return self.restart_pull(data)

    def start_pull_update(self, data=None):
        self._update = True
        return self.restart_pull(data)

    def refresh_product(self, data=None):
        self._update = True
        self._state.pull.process.products = EntityProcess()
        return self.restart_pull(data)

    def restart_push(self, data=None):
        self.init()
        if self._process_type == 'inventory' and self._state.push.resume.process == ModelChannel.PROCESS_PUSHING:
            return
        self._state.push.resume.action = 'display_push'
        self._state.push.resume.type = 'taxes'
        self._state.push.resume.process = ModelChannel.PROCESS_PUSHING

        return self.start_push(data)

    # TODO: PUSH

    def start_push(self, data=None):
        self.log("Starting push " + to_str(self._pid), 'process')
        self.init()
        self._state.finish = False
        self._state.running = True
        self._state.resume.action = self.ACTION_PUSH

        update = {
            'finish': False,
            'running': True,
            'push.resume': self._state.push.resume,
            'resume.action': self.ACTION_PUSH,
            'pid': self._pid,
            'server_id': get_server_id()
        }
        self.get_bridge().update_state(update)
        self.save_sync(status=ModelChannel.PROCESS_PUSHING)
        action = self.get_action_push()
        check_stop = to_int(self.is_stop_process())
        while check_stop not in [FLAG_KILL_ALL, FLAG_STOP]:
            result = getattr(self, action)(data)

            if result['result'] == 'success':
                if self._push_next_action[action]:
                    action = self._push_next_action[action]
                    self._state.push.resume.action = action
                    self.save_push_process(data)
                else:
                    break
            if result['result'] == 'finish':
                break
            time.sleep(0.1)
            check_stop = to_int(self.is_stop_process())
        # if check_stop == FLAG_KILL_ALL:
        # 	self.save_sync()
        # elif check_stop == FLAG_STOP:
        # 	self.save_sync()
        # else:
        # 	self.save_sync()
        self.save_push_process(data)
        self.log("Exiting push " + to_str(self._pid), 'process')

    def display_push(self, data=None):
        self.init()
        if not self.get_channel():
            return Response().error()
        prepare_display_push = self.get_bridge().prepare_display_push()
        if prepare_display_push.result != Response().SUCCESS:
            return prepare_display_push
        self._state = self.get_bridge().get_state()
        self.get_warehouse().set_state(self._state)
        display_push_warehouse = self.get_warehouse().display_push_warehouse()
        if display_push_warehouse.result != Response().SUCCESS:
            return display_push_warehouse
        self._state = self.get_warehouse().get_state()
        self.get_channel().set_state(self._state)
        display_push_channel = self.get_channel().display_push_channel(data)
        if display_push_channel.result != Response().SUCCESS:
            return display_push_channel
        self._state = self.get_channel().get_state()
        self.get_bridge().set_state(self._state)
        display_import = self.get_bridge().display_push()
        if display_import.result != Response().SUCCESS:
            return display_import
        self._state = self.get_bridge().get_state()
        save_state = self.save_state()
        return Response().success()

    def clear_push(self, date=None):
        return Response().success()

    # self.init()
    # if self._state.channel.clear_process.result == Response.SUCCESS:
    # 	return Response().success()
    # clear_data = self.get_channel().clear_channel()
    # self._state = self.get_channel().get_state()
    # if clear_data.result == Response.SUCCESS and self._state.config.taxes:
    # 	prepare_souce = self.get_warehouse().prepare_taxes_export()
    # 	self._state = self.get_warehouse().get_state()
    # 	self.get_channel().set_state(self._state)
    # 	prepare_target = self.get_channel().prepare_taxes_import()
    # 	self._state = self.get_channel().get_state()
    # 	self._state.push.process.taxes.time_start = time.time()
    #
    # 	self._state.push.resume.type = 'taxes'
    #
    # self.save_state()
    # return clear_data

    def prepare_push(self, data=None):
        self.init()
        if not self.get_channel():
            return Response().error()
        prepare_push_warehouse = self.get_warehouse().prepare_push_warehouse(data)
        if prepare_push_warehouse.result != Response().SUCCESS:
            return prepare_push_warehouse
        self._state = self.get_warehouse().get_state()
        self.get_channel().set_state(self._state)
        prepare_push_channel = self.get_channel().prepare_push_channel()
        if prepare_push_channel.result != Response().SUCCESS:
            return prepare_push_channel
        self._state = self.get_channel().get_state()
        self.get_bridge().set_state(self._state)
        prepare_push = self.get_bridge().prepare_push()
        if prepare_push.result != Response().SUCCESS:
            return prepare_push
        self._state = self.get_bridge().get_state()
        save_state = self.save_state()
        return Response().success()

    def push(self, data=None):
        current = self._state.push.resume.type
        if not current:
            current = 'taxes'
        self.init()
        if not self._state:
            return Response().success()
        result = Response().process()
        self._state.push.resume.type = current
        if not self._state.config.get_attribute(current):
            next_action = self._push_next_entity[current]
            result = self.next_entity_push(current, next_action)
            self.save_push_process(data)
            return result
        total = to_int(self._state.push.process[current].total)
        imported = to_int(self._state.push.process[current].imported)
        limit = to_int(self._state.push.process[current].limit)
        error = to_int(self._state.push.process[current].error)
        id_src = to_int(self._state.push.process[current].id_src)
        simple_action = self._import_simple_entity[current]
        next_action = self._push_next_entity[current]
        if total == -1 or imported < total:
            fn_get_main = getattr(self.get_warehouse(),
                                  'get_{}_main_export'.format(current))
            fn_get_ext = getattr(self.get_warehouse(),
                                 'get_{}_ext_export'.format(current))
            fn_convert_export = getattr(
                self.get_warehouse(), 'convert_{}_export'.format(simple_action))
            fn_get_id = getattr(self.get_warehouse(),
                                'get_{}_id_import'.format(simple_action))
            fn_get_updated_time = getattr(
                self.get_warehouse(), 'get_{}_updated_time'.format(simple_action))
            fn_check_import = getattr(
                self.get_channel(), 'check_{}_import'.format(simple_action))
            fn_before_import = getattr(
                self.get_channel(), 'before_{}_import'.format(simple_action))
            fn_import = getattr(self.get_channel(),
                                '{}_channel_import'.format(simple_action))
            fn_insert_map = getattr(
                self.get_channel(), 'insert_map_{}'.format(simple_action))
            fn_after_import = getattr(
                self.get_channel(), 'after_{}_import'.format(simple_action))
            fn_delete_import = getattr(
                self.get_channel(), 'delete_{}_import'.format(simple_action))
            fn_addition_import = getattr(
                self.get_channel(), 'addition_{}_import'.format(simple_action))
            log_times = list()
            start_time = time.time()
            mains = fn_get_main()
            if mains.result != Response.SUCCESS:
                if mains.result == Response.FINISH:
                    return self.next_entity_push(current, next_action)
                else:
                    return Response().create_response(result=Response.STOP_EXPORT)

            # if self._retry >= 5:
            # 	return Response().create_response(result = Response.STOP_EXPORT)
            #
            # self._retry += 1
            # time.sleep(60)
            # self.log("retry get_main_push, sleep 1m", 'retry')
            # return Response().create_response(result = Response.PROCESS)
            self._retry = 0
            ext = fn_get_ext(mains.data)
            if ext.result != Response().SUCCESS:
                self.log('get ext error', 'ext')
                return Response().create_response(result=Response.STOP_EXPORT)
            ext_data = ext.data
            updated_time = 0
            for main in mains.data:
                id_src = fn_get_id(None, main, ext_data)
                updated_time = fn_get_updated_time(main)
                try:
                    if imported >= total and total != -1:
                        break
                    imported += 1
                    start_time = time.time()

                    convert = fn_convert_export(main, ext_data)
                    if current == 'products':
                        # convert = self.get_bridge().assign_template(convert)
                        convert = self.get_channel().assign_template(convert)
                        convert = self.get_channel().apply_channel_setting(convert)
                        convert = self.get_warehouse().update_product_from_channel(convert)
                    if self._warehouse_action and hasattr(self.get_warehouse(), self._warehouse_action):
                        getattr(self.get_warehouse(), self._warehouse_action)(
                            data, convert)
                        continue
                    if self._template_update:
                        self.get_warehouse().product_update_template_data(convert)
                    check_import = fn_check_import(id_src, convert)

                    # if self._channel_action and hasattr(self.get_channel(), self._channel_action):
                    # 	getattr(self.get_channel(), self._channel_action)(check_import, data, convert, ext_data)
                    # 	continue
                    if check_import or self._update:
                        update_data = None
                        if check_import and self._update and hasattr(self.get_channel(), '{}_update'.format(simple_action)):
                            update_data = getattr(self.get_channel(), '{}_update'.format(
                                simple_action))(check_import, convert, main, ext_data)

                        if self._channel_action and hasattr(self.get_channel(), self._channel_action):
                            update_data = getattr(self.get_channel(), self._channel_action)(
                                check_import, data, convert, ext_data)
                        if update_data and hasattr(self.get_warehouse(), f"after_update_{simple_action}"):
                            after_push = getattr(self.get_warehouse(), f"after_update_{simple_action}")(
                                main['_id'], update_data, main)
                        if not self._update and not self._channel_action:
                            after_push = self.after_push(
                                simple_action, main, Response().success(check_import))
                            if after_push and after_push['data']:
                                main = after_push['data']

                        continue
                    if self._channel_action or self._template_update:
                        continue
                    import_data = fn_import(None, main, ext_data)

                    if import_data.result != Response.SUCCESS:
                        if hasattr(self.get_warehouse(), f"after_push_{simple_action}"):
                            after_push = getattr(self.get_warehouse(), f"after_push_{simple_action}")(
                                main['_id'], import_data, main)
                            if after_push and after_push['data']:
                                main = after_push['data']
                        msg = import_data.get('msg')
                        if not msg:
                            msg = "import " + to_str(id_src) + " error"
                        self.log(msg, current + '_errors')

                    if import_data.result == Response.SKIP_ERROR:
                        error += 1
                        continue

                    if import_data.result == Response.ERROR:
                        error += 1
                        if self._state.config.stop_on_error:
                            return Response().create_response(Response.STOP)
                        continue
                    if import_data['result'] == 'warning':
                        if self._state.config.stop_on_error:
                            return Response().create_response(Response.STOP)

                        error += 1
                        continue
                    if import_data.result != Response.SUCCESS:
                        continue
                    id_desc = to_str(import_data.data)
                    try:
                        after_import = fn_after_import(
                            id_desc, convert, main, None)
                    except Exception:
                        self.log_traceback()
                        after_import = Response().error(code=Errors.EXCEPTION_IMPORT)
                    if after_import.result != Response.SUCCESS:
                        fn_delete_import(id_desc)
                        self.after_push(simple_action, main, after_import)
                        continue
                    fn_insert_map(main, main._id, id_desc)
                    self.after_push(simple_action, main, import_data)
                    log_times.append(current + ' id ' + to_str(id_src) + ': ' +
                                     'request target ' + to_str(time.time() - start_time) + 's')
                except Exception:
                    if self._update or self._channel_action:
                        if hasattr(self.get_warehouse(), f"after_update_{simple_action}"):
                            getattr(self.get_warehouse(), f"after_update_{simple_action}")(
                                main['_id'], Response().error(code=Errors.EXCEPTION_IMPORT), main)
                    else:
                        if hasattr(self.get_warehouse(), f"after_push_{simple_action}"):
                            getattr(self.get_warehouse(), f"after_push_{simple_action}")(
                                main['_id'], Response().error(code=Errors.EXCEPTION_IMPORT), main)
                    self.log_traceback(current + '_errors', id_src)
                    if self._state.config.stop_on_error:
                        return Response().create_response(Response.STOP)
                    error += 1
                    continue

            self.log_time(log_times)
            self._state.push.process[current].imported = imported
            if self.get_channel().is_inventory_process() and to_decimal(self._state.push.process[current].updated_time) < updated_time:
                self._state.push.process[current].updated_time = updated_time
            self._state.push.process[current].error = error
            self._state.push.process[current].id_src = id_src
            self.get_channel().set_state(self._state)
            fn_addition_import()
            self._state = self.get_channel().get_state()

        else:

            result = self.next_entity_push(current, next_action)
        if self.get_channel().get_action_stop() or self.get_warehouse().get_action_stop():
            return Response().create_response(Response.STOP_EXPORT)

        self.save_push_process(data)
        return result

    def after_push(self, simple_action, main, import_response):
        after_push = Response().success()
        if hasattr(self.get_warehouse(), f"after_push_{simple_action}"):
            after_push = getattr(self.get_warehouse(), f"after_push_{simple_action}")(
                main['_id'], import_response, main)
        return after_push

    def next_entity_push(self, current, next_action):
        simple_action = self._import_simple_entity[current]

        self.init()
        if hasattr(self.get_warehouse(), 'finish_' + simple_action + '_export'):
            try:
                getattr(self.get_warehouse(), 'finish_' +
                        simple_action + '_export')()
                self._state = self.get_warehouse().get_state()
                self.get_channel().set_state(self._state)

            except Exception:
                self.log_traceback()
        if hasattr(self.get_channel(), 'finish_' + simple_action + '_import'):
            try:
                getattr(self.get_channel(), 'finish_' +
                        simple_action + '_import')()
                self._state = self.get_channel().get_state()

            except Exception:
                self.log_traceback()
        result = Response().process()
        time_finish = time.time()
        self._state.push.process[current].time_finish = to_int(time_finish)
        if next_action:
            if self._state.config.next_action:
                fn_prepare_source = 'prepare_' + next_action + '_export'
                fn_prepare_target = 'prepare_' + next_action + '_import'
                getattr(self.get_warehouse(), fn_prepare_source)()
                self._state = self.get_warehouse().get_state()
                self.get_channel().set_state(self._state)
                getattr(self.get_channel(), fn_prepare_target)()
                self._state = self.get_channel().get_state()
            self._state.push.process[next_action].time_start = time.time()
            self._state.push.process[next_action].time_finish = 0
            self._state.push.resume.type = next_action

        else:
            result.result = 'success'
        return result

    def get_action_push(self):
        resume_process = self._state.push.resume.action
        if resume_process:
            return resume_process
        return 'display_push'

    def finish_push(self, data=None):
        self.init()
        prepare_display_finish = self.get_bridge().prepare_display_finish_push()
        if prepare_display_finish.result != Response.SUCCESS:
            return prepare_display_finish
        self._state = self.get_bridge().get_state()
        self.get_warehouse().set_state(self._state)
        display_finish_warehouse = self.get_warehouse().display_finish_push_warehouse()
        if display_finish_warehouse.result != Response.SUCCESS:
            return display_finish_warehouse
        self._state = self.get_warehouse().get_state()

        self.get_channel().set_state(self._state)
        display_finish_source = self.get_channel().display_finish_channel_push()
        if display_finish_source.result != Response.SUCCESS:
            return display_finish_source
        self._state = self.get_channel().get_state()
        self.get_bridge().set_state(self._state)
        display_finish = self.get_bridge().display_finish_push()
        if display_finish.result != Response.SUCCESS:
            return display_finish
        self._state = self.get_bridge().get_state()
        self._state.push.resume.process = ModelChannel.PROCESS_COMPLETED
        self._state.running = False
        self._state.finish = True
        self.save_state()
        self.save_sync(status=ModelChannel.PROCESS_COMPLETED)
        return Response().success()

    def set_user_id(self, user_id):
        self._user_id = user_id

    def set_state_id(self, state_id):
        self._state_id = state_id
        self.get_bridge().set_state_id(state_id)
        self.get_channel().set_state_id(state_id)
        self.get_warehouse().set_state_id(state_id)

    def set_sync_id(self, sync_id):
        self._sync_id = sync_id

    def set_channel_action(self, action):
        self._channel_action = action

    def set_publish_action(self, publish_action):
        self._publish_action = publish_action

    def set_process_type(self, process_type):
        if not self._process_type:
            self._process_type = process_type

    def init(self, new=False):
        if self._state and self._bridge:
            return self
        self._bridge = ModelChannel()
        self._bridge.set_data(self._data)
        self._bridge.set_is_test(self._test)
        self._bridge.set_user_id(self._user_id)

        if not self._sync_id or new:
            if self._sync_id:
                self._bridge.set_sync_id(self._sync_id)
            self._state = SyncState(
                user_id=self._user_id, sync_id=self._sync_id)
            self.set_process_type('product')
        else:
            self._bridge.set_sync_id(self._sync_id)
            if not self._state:
                self._state = self._bridge.init_state()

            self.set_process_type(self._bridge.get_process_type())
        if not self._user_id:
            self.set_user_id(self._state.user_id)
        self.set_channel_id(self._state.channel.id)
        self._bridge.set_state(self._state)
        self._bridge.set_is_inventory_process(self._is_inventory_process)
        if self._publish_action:
            self._bridge.set_publish_action(self._publish_action)
        self._state_id = self._bridge.get_state_id()
        if self._src_channel_id:
            self._bridge.set_src_channel_id(self._src_channel_id)
        if self._channel_action:
            self._bridge.set_channel_action(self._channel_action)
        if self._channel_default:
            self._bridge.set_db(self._channel_default.get_db())
        return self

    def set_channel_id(self, channel_id):
        self._channel_id = channel_id

    def get_bridge(self):
        '''

        :return: ModelChannel
        '''
        if self._bridge:
            return self._bridge
        self.init()
        return self._bridge

    def get_channel(self):
        if self._channel:
            return self._channel

        channel_type = self._state.channel.channel_type
        channel_version = self._state.channel.config.version
        channel_name, channel_class = self.get_bridge(
        ).get_channel(channel_type, channel_version)
        if not channel_name:
            self._channel = ModelChannel()
        else:
            self._channel = get_model(channel_name, class_name=channel_class)
        if not self._channel:
            return None
        self._channel.set_state(self._state)
        self._channel.set_data(self._data)
        self._channel.set_sync_id(self._sync_id)
        self._channel.set_state_id(self._state_id)
        self._channel.set_is_inventory_process(self._is_inventory_process)
        self._channel.set_db(self.get_bridge().get_db())
        self._channel.set_is_test(self._test)
        self._channel.set_user_id(self._user_id)
        self._channel.set_process_type(self._process_type)
        self._channel.set_template_update(self._template_update)
        if self._publish_action:
            self._channel.set_publish_action(self._publish_action)
        if self._state.channel.name:
            self._channel.set_name(self._state.channel.name)
        if self._state.channel.id:
            self._channel.set_channel_id(self._state.channel.id)
        if self._state.channel.identifier:
            self._channel.set_identifier(self._state.channel.identifier)
        if self._state.channel.url:
            self._channel.set_channel_url(self._state.channel.url)
        if self._state.channel.channel_type:
            self._channel.set_channel_type(self._state.channel.channel_type)
        self._channel.set_date_requested(self._date_requested)
        if self._src_channel_id:
            self._channel.set_src_channel_id(self._src_channel_id)
        if self._channel_action:
            self._channel.set_channel_action(self._channel_action)
        return self._channel

    def get_warehouse(self):
        if self._warehouse:
            return self._warehouse
        self._warehouse = ModelWareHouse()
        self._warehouse.set_data(self._data)
        self._warehouse.set_state(self._state)
        self._warehouse.set_channel_id(self._state.channel.id)
        self._warehouse.set_sync_id(self._sync_id)
        self._warehouse.set_db(self.get_bridge().get_db())
        self._warehouse.set_is_test(self._test)
        self._warehouse.set_state_id(self._state_id)
        self._warehouse.set_user_id(self._user_id)
        self._warehouse.set_date_requested(self._date_requested)
        self._warehouse.set_process_type(self._process_type)
        self._warehouse.set_is_inventory_process(self._is_inventory_process)
        self._warehouse.set_template_update(self._template_update)
        if self._publish_action:
            self._channel.set_publish_action(self._publish_action)
        if self._src_channel_id:
            self._warehouse.set_src_channel_id(self._src_channel_id)
        if self._channel_action:
            self._warehouse.set_channel_action(self._channel_action)
        return self._warehouse

    def get_channel_default(self):
        if self._channel_default is not None:
            return self._channel_default
        if not self._state:
            bridge = ModelChannel()
            bridge.set_user_id(self._user_id)
            bridge.set_data(self._data)
        else:
            bridge = self.get_bridge()
        channel_default_data = bridge.get_channel_default()
        if not channel_default_data:
            self._channel_default = False
            return False
        channel_default_process = bridge.get_process_by_type(
            ModelChannel.PROCESS_TYPE_PRODUCT, channel_default_data['id'])
        state_default = bridge.get_state_by_id(
            channel_default_process['state_id'])
        channel_version = state_default.channel.config.version
        channel_name, channel_class = bridge.get_channel(
            channel_default_data['type'], channel_version)
        if not channel_name:
            self._channel_default = ModelChannel()
        else:
            self._channel_default = get_model(
                channel_name, class_name=channel_class)
        if not self._channel_default:
            return None
        self._channel_default.set_data(self._data)
        self._channel_default.set_state(state_default)
        self._channel_default.set_sync_id(channel_default_process['id'])
        self._channel_default.set_state_id(channel_default_process['state_id'])
        self._channel_default.set_is_inventory_process(False)
        self._channel_default.set_db(bridge.get_db())
        self._channel_default.set_is_test(self._test)
        self._channel_default.set_user_id(self._user_id)
        self._channel_default.set_process_type(self._process_type)
        self._channel_default.set_channel_id(channel_default_data['id'])
        if state_default.channel.name:
            self._channel_default.set_name(state_default.channel.name)
        if state_default.channel.id:
            self._channel_default.set_id(state_default.channel.id)
        if state_default.channel.identifier:
            self._channel_default.set_identifier(
                state_default.channel.identifier)
        if state_default.channel.url:
            self._channel_default.set_channel_url(state_default.channel.url)
        if state_default.channel.channel_type:
            self._channel_default.set_channel_type(
                state_default.channel.channel_type)
        self._channel_default.set_date_requested(self._date_requested)
        return self._channel_default

    def save_state(self):
        if not self._refresh:
            return self.get_bridge().save_state()
        return True

    def save_sync(self, **kwargs):
        if self._refresh:
            return True
        if 'pid' not in kwargs:
            kwargs['pid'] = self._pid
        return self.get_bridge().save_sync(**kwargs)

    # TODO: CART

    def cart_display_pull(self, data=None):
        cart_display_pull = self.get_channel().display_pull_channel()
        if cart_display_pull.result != Response().SUCCESS:
            return cart_display_pull
        return Response().success()

    def cart_pull(self, data=None):
        if not self._refresh:
            start_migration = self.get_channel().start_migration(data)
            if start_migration.result != Response().SUCCESS:
                return start_migration
            return Response().success()
        return self.pull(data)

    def cart_finish_pull(self, data=None):
        finish_pull = self.finish_pull(data)
        if self._process_type and hasattr(self.get_warehouse(), f"finish_{self._process_type}_import"):
            getattr(self.get_warehouse(),
                    f"finish_{self._process_type}_import")()
        return finish_pull

    def addition_order_import(self):
        if self._state.channel.default:
            return
        channel_default = self.get_channel_default()
        if not channel_default:
            return
        addition = channel_default.addition_order_import()
        return True

    def finish_order_import(self, order_id, order: Order):
        if self._state.channel.default:
            return
        channel_default = self.get_channel_default()
        if not channel_default:
            return
        if order.link_status != Order.LINKED:
            import_data = Response().error(msg='Product in order not link')
            self.get_warehouse().after_create_order_sync(
                order_id, channel_default.get_channel_id(), import_data, order)
            return Response().success()

        order_ext = self.get_warehouse().get_orders_ext_export([order])
        convert_order = self.get_warehouse().convert_order_export(
            order, order_ext.data, channel_id=channel_default.get_channel_id())
        if convert_order.result != Response.SUCCESS:
            self.get_warehouse().after_create_order_sync(
                order_id, channel_default.get_channel_id(), convert_order, order)
        setting_order = True if self._state.channel.config.setting.get(
            'order', {}).get('status') != 'disable' else False
        channel_default.channel_order_sync_inventory(order, setting_order)
        if setting_order:
            try:
                order_import = channel_default.order_import(
                    None, convert_order['data'], None)
            except Exception:
                self.log_traceback()
                order_import = Response().error()
            self.get_warehouse().after_create_order_sync(
                order_id, channel_default.get_channel_id(), order_import, convert_order['data'])
            if order_import.result != Response.SUCCESS:
                return
            channel_default.after_order_import(
                order_import.data[0], order, None, None)
        return

    def finish_order_update(self, order_id, channel_order_id, order: Order, current_order: Order):
        channel_default = self.get_channel_default()
        if not channel_default:
            return
        if order.link_status != Order.LINKED:
            return Response().success()

        order_ext = self.get_warehouse().get_orders_ext_export([order])
        convert_order = self.get_warehouse().convert_order_export(
            order, order_ext.data, channel_id=channel_default.get_channel_id())
        if convert_order.result != Response.SUCCESS:
            return Response().success()
        state = self.get_channel().get_state()
        setting_order = True if state.channel.config.setting.get(
            'order', {}).get('status') != 'disable' else False

        channel_default.after_order_update(
            channel_order_id, order_id, convert_order.data, current_order, setting_order)
        return

    def finish_product_update(self, product_id, channel_product_id, product: Product, current_product: Product):
        if self.get_channel().get_channel_type() != 'bulk_edit':
            return
        channel_default = self.get_channel_default()
        if not channel_default:
            return
        check_import = channel_default.check_product_import(
            product_id, product)
        if not check_import:
            return
        state = self.get_warehouse().get_state()
        channel_id = self.get_warehouse().get_channel_id()
        self.get_warehouse().set_channel_id(channel_default.get_channel_id())
        self.get_warehouse().set_state(channel_default.get_state())
        product_ext = self.get_warehouse().get_products_ext_export([product])
        convert_product = self.get_warehouse().convert_product_export(
            product, product_ext.data)
        channel_default.product_channel_update(
            check_import, convert_product, None)
        self.get_warehouse().set_channel_id(channel_id)
        self.get_warehouse().set_state(state)
        return

    def finish_product_import(self, product_id, product: Product):
        if not self._data.get('auto_import'):
            return Response().success()
        src_channel_id = self.get_warehouse().get_channel_id()
        state = self.get_warehouse().get_state()
        for channel_id in self._data['auto_import']:
            channel = self.get_channel_product(channel_id)
            if not channel:
                continue
            self.get_warehouse().set_channel_id(channel_id)
            self.get_warehouse().set_src_channel_id(src_channel_id)
            self.get_warehouse().set_state(channel.get_state())
            product = channel.add_product_to_draft(
                product_id, product, assign_template=False)
            # self.get_warehouse().set_src_channel_id(None)

            product_ext = self.get_warehouse(
            ).get_products_ext_export([product])
            convert_product = self.get_warehouse().convert_product_export(
                product, product_ext.data)
            if convert_product.variants:
                for variant in convert_product.variants:
                    variant = channel.add_product_to_draft(
                        variant['_id'], variant, assign_template=False)
            if channel.get_channel_type() in ['ebay', 'amazon']:
                continue
            convert_product = channel.assign_template(convert_product)
            convert_product = channel.apply_channel_setting(convert_product)
            convert_product = self.get_warehouse().update_product_from_channel(convert_product)
            check_import = channel.check_product_import(
                product['_id'], convert_product)
            if check_import:
                continue
            try:
                product_import = channel.product_import(
                    None, convert_product, None)
            except Exception:
                self.log_traceback()
                product_import = Response().error()
            if product_import.result != Response.SUCCESS:
                self.get_warehouse().after_create_product_sync(
                    product_id, channel_id, product_import, product, src_channel_id)
                continue
            try:
                after_import = channel.after_product_import(
                    product_import.data, product, product, None)
            except Exception:
                self.log_traceback()
                after_import = Response().error()
            if after_import.result != Response.SUCCESS:
                self.get_warehouse().after_create_product_sync(
                    product_id, channel_id, after_import, product, src_channel_id)
                channel.delete_product_import(product_import.data)
                continue
            self.get_warehouse().after_create_product_sync(
                product_id, channel_id, product_import, product, src_channel_id)
        self.get_warehouse().set_channel_id(src_channel_id)
        self.get_warehouse().set_src_channel_id(src_channel_id)
        self.get_warehouse().set_state(state)
        return

    def channel_action(self, data):
        model_channel = ModelChannel()
        model_channel.set_data(self._data)
        process = model_channel.get_process_by_type(
            ModelChannel.PROCESS_TYPE_PRODUCT, data['channel_id'])
        if not process:
            return Response().success()
        self.set_sync_id(process['id'])
        self.set_channel_action(data['action'])
        self.set_publish_action(data['action'])
        self.init()
        self._state.resume.description = data['action']
        return self.restart_push(data)

    def delete_product(self, data=None):
        model_channel = ModelChannel()
        model_channel.set_data(self._data)
        process = model_channel.get_process_by_type(
            ModelChannel.PROCESS_TYPE_PRODUCT, data['channel_id'])
        if not process:
            return Response().success()
        self.set_sync_id(process['id'])
        self.init()
        self.get_warehouse().product_deleted(data['product_id'])
        return Response().success()

    def bulk_delete_product(self, data=None):
        model_channel = ModelChannel()
        model_channel.set_data(self._data)
        process = model_channel.get_process_by_type(
            ModelChannel.PROCESS_TYPE_PRODUCT, data['channel_id'])
        if not process:
            return Response().success()
        self.set_sync_id(process['id'])
        self.init()
        product_ids = data['product_ids']
        for product_id in product_ids:
            self.get_warehouse().product_deleted(product_id)
        return Response().success()

    def bulk_edit_product(self, data):
        self.init()
        self._state.pull.resume.action = ''
        self._state.pull.resume.process = ModelChannel.PROCESS_PULLING
        self._state.pull.resume.type = 'products'
        self._update = True
        self._import = False
        return self.start_pull(data)

    def get_default_state(self, data=None):
        state = SyncState()
        return state
