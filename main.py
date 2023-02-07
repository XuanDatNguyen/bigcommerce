from flask import Blueprint, request as flask_request, jsonify
from flasgger import Swagger
from flask import Flask, request
from flask_cors import CORS

from app.main.middleware.auth import Auth
from app.main.route.cart import cart_path
from app.main.route.category import category_path
from app.main.route.channel import channel_path
from app.main.route.cron import cron_path
from app.main.route.order import order_path
from app.main.route.process import process_path
from app.main.route.product import product_path
from app.main.route.route import route_path
from app.main.route.server import server_path
from datasync.libs.utils import *
from datasync.models.modes.test import ModelModesTest

ROOT_DIR = get_root_path()

mode = get_config_ini('local', 'mode')
if mode == 'live':
    api_url = get_config_ini('server', 'api_url')
    if not api_url:
        print(
            "Please add api_url in file datasync/etc/config.ini.sample under section server")
        sys.exit()
elif mode == 'test':
    model_test = ModelModesTest()
    model_test.setup()
app = Flask(__name__, template_folder=os.path.join(
    ROOT_DIR, 'app', 'documents', 'templates'))
swagger_config = {
    "headers": [
    ],
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,  # all in
                        "model_filter": lambda tag: True,  # all in
        }
    ],
    "static_url_path": "/flasgger_static",
    # "static_folder": "static",  # must be set by user
    "swagger_ui": True,
    "specs_route": "/sync_docs/",
}

swagger = Swagger(app, template_file=os.path.join(
    ROOT_DIR, 'app', 'documents', 'swagger.yml'), config=swagger_config)

app.wsgi_app = Auth(app.wsgi_app)
app.debug = to_bool(get_config_ini('local', 'debug', False))
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
# scheduler = APScheduler()
# scheduler.init_app(app)
# scheduler.start()


@app.route("/hello", methods=['post', 'get'])
@app.route("/hello/<string:name>/", methods=['post', 'get'])
def hello(name=None):
    return 'hello' + (name if name else '')


if not to_bool(get_config_ini('local', 'debug')):
    @app.errorhandler(500)
    def internal_server_error(error):
        app_log = get_config_ini('local', 'app_log')
        if not app_log:
            app_log = APP_LOG_DAILY
        if app_log == APP_LOG_SINGLE:
            file_log = 'exceptions.log'
        elif app_log == APP_LOG_DAILY:
            file_log = 'exceptions_{}.log'.format(get_current_time("%Y-%m-%d"))
        else:
            file_log = get_config_ini('local', 'log_file', 'exceptions.log')
        file_log = get_pub_path() + '/log/flask/' + file_log
        folder_log = os.path.dirname(file_log)
        if not os.path.isdir(folder_log):
            os.makedirs(folder_log)
            change_permissions_recursive(folder_log, 0x777)
        msg = '{}: \nPath: {}\nMethod: {}\nData: {}\nResponse status: 500\nError: {}'
        ts = time.strftime('%Y/%m/%d %H:%M:%S')
        data = request.data.decode()
        if data and (isinstance(data, list)) or isinstance(data, dict):
            data = json_encode(data)
        msg = msg.format(ts, request.full_path, request.method,
                         data, traceback.format_exc())
        check_exist = False
        if os.path.isfile(file_log):
            check_exist = True
        with open(file_log, 'a') as log_file:
            log_file.write(msg)
        if not check_exist and os.path.isfile(file_log):
            os.chmod(file_log, 0o777)
        return error.args[0], error.code
else:
    @app.errorhandler(Exception)
    def all_exception_error(error):
        app_log = get_config_ini('local', 'app_log')
        if not app_log:
            app_log = APP_LOG_DAILY
        if app_log == APP_LOG_SINGLE:
            file_log = 'exceptions.log'
        elif app_log == APP_LOG_DAILY:
            file_log = 'exceptions_{}.log'.format(get_current_time("%Y-%m-%d"))
        else:
            file_log = get_config_ini('local', 'log_file', 'exceptions.log')
        file_log = get_pub_path() + '/log/flask/' + file_log
        folder_log = os.path.dirname(file_log)
        if not os.path.isdir(folder_log):
            os.makedirs(folder_log)
            change_permissions_recursive(folder_log, 0x777)
        msg = '{}: \nPath: {}\nMethod: {}\nData: {}\nResponse status: {}\nError: {}'
        ts = time.strftime('%Y/%m/%d %H:%M:%S')
        data = request.data.decode()
        if data and (isinstance(data, list)) or isinstance(data, dict):
            data = json_encode(data)
        response_status = 500
        if hasattr(error, 'code'):
            response_status = error.code
        msg = msg.format(ts, request.full_path, request.method,
                         data, response_status, traceback.format_exc())
        check_exist = False
        if os.path.isfile(file_log):
            check_exist = True
        with open(file_log, 'a') as log_file:
            log_file.write(msg)
        if not check_exist and os.path.isfile(file_log):
            os.chmod(file_log, 0o777)
        msg_error = error.args[0] if len(error.args) > 0 else (
            error.description if hasattr(error, 'description') else '')
        code = error.code if hasattr(error, 'code') else 500
        return msg_error, code
pub_folder = get_pub_path()
if not os.path.isdir(pub_folder):
    os.makedirs(pub_folder, 0o777)
    os.makedirs(os.path.join(pub_folder, 'log'), 0o777)
    os.makedirs(os.path.join(pub_folder, 'media'), 0o777)
    os.makedirs(os.path.join(pub_folder, 'uploads'), 0o777)
change_permissions_recursive(pub_folder, 0o777)

app.register_blueprint(channel_path, url_prefix='/api/v1')
app.register_blueprint(product_path, url_prefix='/api/v1')
app.register_blueprint(category_path, url_prefix='/api/v1')
app.register_blueprint(process_path, url_prefix='/api/v1')
app.register_blueprint(server_path, url_prefix='/api/v1')
app.register_blueprint(order_path, url_prefix='/api/v1')
app.register_blueprint(cron_path, url_prefix='/api/v1')
app.register_blueprint(route_path, url_prefix='/api/v1')
app.register_blueprint(
    cart_path, url_prefix='/api/v1/merchant/<string:cart_type>/webhook')


if __name__ == '__main__':
    port = to_int(get_config_ini('local', 'port'))
    app.run(host='0.0.0.0', port=port)
