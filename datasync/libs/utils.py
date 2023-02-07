import jwt
import time
import base64
import configparser
import hashlib
import hmac
import html
import importlib
import json
import math
import os
import random
import re
import shutil
import socket
import struct
import subprocess
import sys
import traceback
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from uuid import UUID

import six
import xmltodict
from bs4 import BeautifulSoup
from bson import ObjectId
from flask import request as flask_request
from packaging import version
from phpserialize import *

# from libs.base_thread import BaseThread
from datasync.libs.prodict import Prodict

LIMIT_LINE_ERROR = 200
COLLETION_state = 'state'
MIGRATION_FULL = 2
MIGRATION_DEMO = 1
GROUP_USER = 1
GROUP_TEST = 2
STATUS_NEW = 1
STATUS_RUN = 2
STATUS_STOP = 3
STATUS_COMPLETED = 4
STATUS_KILL = 5
STATUS_CONFIGURING = 6
STATUS_PAYMENT = 7
DIR_UPLOAD = 'uploads'
BASE_DIR = 'datasync'

CONFIG_FILE = 'datasync/etc/docs.ini'
DIR_PROCESS = 'processes/'
FLAG_STOP = 1
FLAG_KILL_ALL = 2
APP_LOG_SINGLE = 'single'
APP_LOG_DAILY = 'daily'
APP_LOG_CUSTOM = 'custom'
LOG_SINGLE = ('process',)


class Authorization:
    PREFIX = 'lit'

    def __init__(self, **kwargs):
        self._private_key = kwargs.get(
            'private_key', get_config_ini('local', 'private_key'))
        self._user_id = kwargs.get('user_id')

    def encode(self, data=None, insert_prefix=True):
        if not data:
            data = dict()
        data['time'] = str(int(time.time()))
        data['user_id'] = self._user_id
        jwt_token = jwt.encode(data, self._private_key, algorithm='HS256')
        if isinstance(jwt_token, bytes):
            jwt_token = jwt_token.decode()
        if insert_prefix:
            jwt_token = f"{self.PREFIX} {jwt_token}"
        return jwt_token

    def decode(self, authorization):
        if not authorization or not isinstance(authorization, str):
            return False
        authorization = authorization.split(' ')
        if len(authorization) != 2 and authorization[0] != self.PREFIX:
            return False
        try:
            data = jwt.decode(
                authorization[1], self._private_key, algorithms=['HS256'])
        except jwt.exceptions.InvalidSignatureError as e:
            return False
        except Exception as e:
            return False
        return data

    def get_user_id(self, authorization):
        data = self.decode(authorization)
        if not data:
            return self.get_user_id_default()
        return data.get('user_id', self.get_user_id_default())

    def get_user_id_from_flask_request(self):
        authorization = flask_request.environ.get('HTTP_AUTHORIZATION')
        if not authorization:
            return self.get_user_id_default()
        return self.get_user_id(authorization)

    def get_user_id_default(self):
        if to_bool(get_config_ini('local', 'is_local')):
            return get_config_ini('local', 'user_id_default')
        return 0


def get_value_by_key_in_dict(dictionary, key, default=None):
    if not dictionary or not isinstance(dictionary, dict):
        return default
    if key in dictionary:
        return dictionary[key] if dictionary[key] else default
    return default


def check_pid(pid):
    if not to_int(pid):
        return False
    pid = to_int(pid)
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def get_controller(controller_name, data=None):
    # if controller_name == 'base':
    # 	if data:
    # 		my_instance = BaseThread(data)
    # 	else:
    # 		my_instance = BaseThread()
    # 	return my_instance
    try:
        module_class = importlib.import_module(
            BASE_DIR + '.controllers.' + controller_name)
    except Exception as e:
        log_traceback()
        return None
    class_name = "Controller{}".format(controller_name.capitalize())
    my_class = getattr(module_class, class_name)
    # if data:
    my_instance = my_class(data)
    # else:
    # 	my_instance = my_class()
    return my_instance


def get_model(name, data=None, class_name=None):
    if not name:
        return None
    # name_path = name.replace('_', '/')
    file_path = os.path.join(get_root_path(), BASE_DIR,
                             'models', *name.split('.')) + '.py'
    file_model = Path(file_path)
    if not file_model.is_file():
        return None
    name_path = name.split('_')
    model_name = BASE_DIR + ".models." + name.replace('/', '.')
    module_class = importlib.import_module(model_name)
    class_name = class_name if class_name else get_model_class_name(name)

    try:
        model_class = getattr(module_class, class_name)
        if data:
            model = model_class(data)
        else:
            model = model_class()
        return model
    except Exception as e:
        log_traceback(type_error='get_model')
        return None


def get_model_class_name(name, char='/'):
    name = name.replace(BASE_DIR, '')
    split = re.split(r'[^a-z0-9]', name)
    upper = list(map(lambda x: x.capitalize(), split))
    new_name = 'Model' + ''.join(upper)
    return new_name


def md5(s, raw_output=False):
    res = hashlib.md5(s.encode())
    if raw_output:
        return res.digest()
    return res.hexdigest()


def hash_hmac(algo, data, key):
    res = hmac.new(key.encode(), data.encode(), algo).hexdigest()
    return to_str(res)


def to_str(value):
    if isinstance(value, bool):
        return str(value)
    if (isinstance(value, int) or isinstance(value, float)) and value == 0:
        return '0'
    if not value:
        return ''
    if isinstance(value, dict) or isinstance(value, list):
        return json_encode(value)
    if hasattr(value, 'to_json'):
        return getattr(value, 'to_json')()
    try:
        value = str(value)
        return value
    except Exception:
        return ''


def change_permissions_recursive(path, mode=0o755):
    os.chmod(path, mode)
    for root, dirs, files in os.walk(path):
        for sub_dir in dirs:
            os.chmod(os.path.join(root, sub_dir), mode)
        for sub_file in files:
            os.chmod(os.path.join(root, sub_file), mode)


def to_timestamp_or_false(value, str_format='%Y-%m-%d %H:%M:%S', limit_len=True):
    if limit_len:
        value = value[0:19]
    try:
        timestamp = int(time.mktime(time.strptime(value, str_format)))
        if timestamp:
            return timestamp
        return False
    except:
        return False


def to_timestamp(value, str_format='%Y-%m-%d %H:%M:%S', limit_len=True):
    if limit_len:
        value = value[0:19]
    try:
        timestamp = int(time.mktime(time.strptime(value, str_format)))
        if timestamp:
            return timestamp
        return int(time.time())
    except:
        return int(time.time())


def to_int(value):
    if not value:
        return 0
    try:
        value = int(float(value))
        return value
    except Exception:
        return 0


def to_bool(value):
    if isinstance(value, str):
        if value.lower().strip() == 'false':
            return False
    if value:
        return True
    return False


def to_object_id(value):
    try:
        value = ObjectId(value)
        return value
    except Exception:
        return False


def to_decimal(value, length=None):
    if not value:
        return 0.00
    try:
        value = round(float(value), length) if length else float(value)
        return value
    except Exception:
        return 0.00


def to_len(value):
    if not value:
        return 0
    try:
        res = len(value)
    except Exception:
        res = 0
    return res


def isoformat_to_datetime(value):
    if len(value) == 25:
        value = value[0:22] + value[23:]
    try:
        data = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        data = datetime.strptime(value[0:19], "%Y-%m-%dT%H:%M:%S")
    return data


def dict_key_to_str(dict_data: dict):
    if not dict_data:
        return dict_data
    new_data = dict()
    for k, v in dict_data.items():
        k = str(k)
        if isinstance(v, dict):
            v = dict_key_to_str(v)
        new_data[k] = v
    return new_data


def convert_format_time(time_data, old_format='%Y-%m-%d %H:%M:%S', new_format='%Y-%m-%d %H:%M:%S', limit_length=True):
    if to_int(re.sub('[^0-9]', '', to_str(time_data))) == 0:
        return None
    try:
        if to_str(time_data).isnumeric():
            timestamp = datetime.fromtimestamp(time_data)
            res = timestamp.strftime(new_format)
            return res
        if not old_format:
            old_format = '%Y-%m-%d %H:%M:%S'
        time_data = time_data[0:19] if limit_length else time_data
        new_time = datetime.strptime(time_data, old_format)
        res = new_time.strftime(new_format)
        return res

    except Exception:
        return get_current_time(new_format)


def print_time(thread_name):
    time.sleep(10)
    print("%s: %s" % (thread_name, time.ctime(time.time())))


def gmdate(str_format, int_time_stamp=None):
    if not int_time_stamp:
        return time.strftime(str_format, time.gmtime())
    else:
        return time.strftime(str_format, time.gmtime(int_time_stamp))


def log(msg, prefix_path=None, type_error='exceptions'):
    prefix_path = to_str(prefix_path)
    type_error = to_str(type_error.replace('.log', ''))
    app_log = get_config_ini('local', 'app_log')
    if not app_log:
        app_log = APP_LOG_DAILY
    if app_log == APP_LOG_SINGLE or type_error in LOG_SINGLE:
        file_log = '{}.log'.format(type_error)
    elif app_log == APP_LOG_DAILY:
        file_log = '{}_{}.log'.format(type_error, get_current_time("%Y-%m-%d"))
    else:
        file_log = get_config_ini('local', 'log_file', 'exceptions.log')
    file_log = os.path.join(get_pub_path(), 'log', prefix_path, file_log)
    folder_log = os.path.dirname(file_log)
    if not os.path.isdir(folder_log):
        os.makedirs(folder_log)
        change_permissions_recursive(folder_log, 0o777)
    if os.path.exists(file_log) and os.path.getsize(file_log) >= 10485760:
        os.remove(file_log)
    msg_log = '{}: \n{}'

    msg = to_str(msg)
    ts = time.strftime('%Y/%m/%d %H:%M:%S')
    msg_log = msg_log.format(ts, msg).rstrip('\n')
    msg_log += "\n{}\n".format("-" * 100)
    check_exist = False
    if os.path.isfile(file_log):
        check_exist = True
    with open(file_log, 'a') as log_file:
        log_file.write(msg_log)
    if not check_exist and os.path.isfile(file_log):
        os.chmod(file_log, 0o777)


def clear_log(migration_id):
    if not migration_id:
        return response_success()
    path = get_pub_path() + '/log/' + str(migration_id)
    if os.path.isdir(path):
        shutil.rmtree(path)
    return response_success()


def log_traceback(prefix=None, type_error='exceptions'):
    error = traceback.format_exc()
    log(error, prefix, type_error)


def get_default_format_date():
    return "%Y-%m-%d %H:%M:%S"


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


def get_current_time(str_format='%Y-%m-%d %H:%M:%S'):
    try:
        current_time = time.strftime(str_format)
    except Exception:
        current_time = time.strftime(get_default_format_date())
    return current_time


def ip2long(ip):
    """
    Convert an IP string to long
    """
    try:
        packedIP = socket.inet_aton(ip)
        res = struct.unpack("!L", packedIP)[0]
    except Exception:
        res = ''
    return res


# response
def create_response(result='', msg='', data=None):
    return Prodict(**{'result': result, 'msg': msg, 'data': data})


def response_error(msg=''):
    return create_response('error', msg)


def response_api(msg=''):
    return create_response('api', msg)


def response_success(data=None, msg=''):
    return create_response('success', msg, data)


def response_warning(msg=None):
    return create_response('warning', msg)


# base64
def string_to_base64(s):
    if not isinstance(s, str):
        s = str(s)
    return base64.b64encode(s.encode('utf-8')).decode('utf-8')


def base64_to_string(b):
    try:
        s = base64.b64decode(b).decode('utf-8')
        return s
    except Exception as e:
        try:
            s = base64.b64decode(b.encode('utf-8')).decode('utf-8')
            return s
        except Exception as e:
            # log_traceback()
            return None


def php_serialize(obj):
    try:
        res = serialize(obj).decode('utf-8')
    except Exception as e:
        res = False
    return res


def php_unserialize(str_serialize):
    try:
        res = unserialize(str_serialize.encode('utf-8'))
    except Exception:
        try:
            res = unserialize(str_serialize)
        except Exception:
            res = False
    res = decode_after_unserialize(res)
    if isinstance(res, dict):
        keys = list(res.keys())
        keys = list(map(lambda x: to_str(x), keys))
        keys.sort()
        for index, key in enumerate(keys):
            if to_str(index) != to_str(key):
                return res
        res = list(res.values())
    return res


def decode_after_unserialize(data):
    res = None
    if isinstance(data, dict):
        res = dict()
        for k, v in data.items():
            try:
                key = k.decode('utf-8')
            except Exception:
                key = k
            if isinstance(v, dict):
                value = decode_after_unserialize(v)
            else:
                try:
                    value = v.decode('utf-8')
                except Exception:
                    value = v
            res[key] = value
    elif isinstance(data, list):
        res = list()
        for row in data:
            value = decode_after_unserialize(row)
            res.append(value)
    else:
        try:
            res = data.decode('utf-8')
        except Exception:
            res = data
    return res


# Get one array from list array by field value
def get_row_from_list_by_field(data, field, value):
    result = dict()
    if not data or not field:
        return result
    for row in data:
        if (field in row) and str(row[field]) == str(value):
            result = row
            break
    return result


# Get array value from list array by field value and key of field need
def get_row_value_from_list_by_field(data, field, value, need):
    if not data:
        return False
    row = get_row_from_list_by_field(data, field, value)
    if not row:
        return False
    row = dict(row)
    return row.get(need, False)


# Get and unique array value by key
def duplicate_field_value_from_list(data, field):
    result = list()
    if not data:
        return result
    data = list(data)
    for item in data:
        if to_str(field) in item:
            result.append(item[field])
    result = list(set(result))
    return result


# Get list array from list by list field value
def get_list_from_list_by_list_field(data, field, values):
    if not data or not field:
        return list()
    if not isinstance(data, list):
        values = [values]
    values = list(map(lambda x: to_str(x), values))
    result = list()
    try:
        for row in data:
            if to_str(row[field]) in values:
                result.append(row)
    except Exception:
        return list()
    return result


# Get list array from list by field  value
def get_list_from_list_by_field(data, field, value):
    if not data:
        return list()
    result = list()
    try:
        for row in data:
            if isinstance(value, list):
                for item in value:
                    if to_str(row[field]) == to_str(item):
                        result.append(row)
            else:
                if to_str(row[field]) == to_str(value):
                    result.append(row)
    except Exception:
        return list()
    return result


# url
def strip_domain_from_url(url):
    parse = urllib.parse.urlparse(url)
    path_url = parse.path
    query = parse.query
    fragment = parse.fragment
    if query:
        path_url += '?' + query
    if fragment:
        path_url += '#' + fragment
    return path_url


def join_url_path(url, path_url):
    full_url = url.rstrip('/')
    if path_url:
        full_url += '/' + path_url.lstrip('/')
    return full_url


def send_data_socket(data, conn):
    if isinstance(data, list) or isinstance(data, dict):
        data = json_encode(data)
    data = str(data).encode('utf-8')
    conn.send(data)
    conn.close()


def get_root_path():
    path = os.path.dirname(os.path.abspath(__file__))
    path = path.replace('/datasync/libs', '')
    return path


def get_pub_path():
    path = get_root_path()
    if 'pub' in path:
        index = path.find('pub')
        path = path[0:index]
    path = path.rstrip('/') + '/pub'
    return path


def console_success(msg):
    result = '<p class="success"> - ' + msg + '</p>'
    return result


def console_error(msg):
    result = '<p class="error"> - ' + msg + '</p>'
    return result


def console_warning(msg):
    result = '<p class="warning"> - ' + msg + '</p>'
    return result


# json
def json_decode(data):
    try:
        data = json.loads(data)
    except Exception:
        try:
            data = json.loads(data.decode('utf-8'))
        except Exception:
            data = False
    return data if isinstance(data, (list, dict)) else False


def json_encode(data):
    try:
        data = json.dumps(data)
    except Exception:
        data = False
    return data


def clone_code_for_migration_id(migration_id):
    if check_folder_clone(migration_id):
        return True
    base_dir = get_pub_path() + '/' + DIR_PROCESS + to_str(migration_id)
    if not os.path.isdir(base_dir):
        os.makedirs(base_dir)
    folder_copy = ['controllers', 'libs', 'models']
    file_copy = ['bootstrap.py']
    for folder in folder_copy:
        if os.path.isdir(base_dir + '/' + BASE_DIR + '/' + folder):
            continue
        shutil.copytree(BASE_DIR + '/' + folder, base_dir +
                        '/' + BASE_DIR + '/' + folder)
    for file in file_copy:
        if os.path.isfile(base_dir + '/' + file):
            continue
        shutil.copy(file, base_dir + '/' + file)

    git_ignore_file = base_dir + '/' + '.gitignore'
    f = open(git_ignore_file, "w+")
    f.write('*')
    change_permissions_recursive(base_dir, 0o777)


def clone_code(prefix):
    if check_folder_clone(prefix):
        return True
    destination_dir = os.path.join(get_pub_path(), 'clone', prefix, BASE_DIR)
    base_dir = os.path.join(get_root_path(), BASE_DIR)
    if not os.path.isdir(destination_dir):
        os.makedirs(destination_dir)
    folder_copy = ['controllers', 'libs', 'models']
    file_copy = ['bootstrap.py']
    for folder in folder_copy:
        if os.path.isdir(os.path.join(destination_dir, folder)):
            continue
        shutil.copytree(os.path.join(base_dir, folder),
                        os.path.join(destination_dir, folder))
    for file in file_copy:
        if os.path.isfile(os.path.join(destination_dir, '..', file)):
            continue
        shutil.copy(os.path.join(get_root_path(), file),
                    os.path.join(destination_dir, '..', file))

    git_ignore_file = destination_dir + '/' + '.gitignore'
    f = open(git_ignore_file, "w+")
    f.write('*')
    change_permissions_recursive(destination_dir, 0o777)


def clone_code_for_user(user_id):
    prefix = os.path.join('users', to_str(user_id))
    clone_code(prefix)


def clone_code_for_process(process_id):
    prefix = os.path.join(DIR_PROCESS, to_str(process_id))
    clone_code(prefix)


# destination_dir = os.path.join(get_pub_path(), DIR_PROCESS, to_str(process_id), BASE_DIR)
# base_dir = os.path.join(get_root_path(), BASE_DIR)
# if not os.path.isdir(destination_dir):
# 	os.makedirs(destination_dir)
# folder_copy = ['controllers', 'libs', 'models']
# file_copy = ['bootstrap.py']
# for folder in folder_copy:
# 	if os.path.isdir(os.path.join(destination_dir, folder)):
# 		continue
# 	shutil.copytree(os.path.join(base_dir, folder), os.path.join(destination_dir, folder))
# for file in file_copy:
# 	if os.path.isfile(os.path.join(destination_dir, '..', file)):
# 		continue
# 	shutil.copy(os.path.join(get_root_path(), file), os.path.join(destination_dir, '..', file))
#
# git_ignore_file = destination_dir + '/' + '.gitignore'
# f = open(git_ignore_file, "w+")
# f.write('*')
# change_permissions_recursive(destination_dir, 0o777)


def start_subprocess(buffer=None, wait=False):
    data = buffer.get('data') or dict()
    if not data.get('user_id'):
        user_id = Authorization().get_user_id_from_flask_request()
        data['user_id'] = user_id
        buffer['data'] = data
    sync_id = to_str(data.get('sync_id'))
    user_id = to_str(data.get('user_id'))
    list_special = ['reset_migration', 'clone_migration', 'stop_auto_test',
                    'restart_migration', 'kill_end_loop_migration', 'kill_migration', 'delete_migration']
    action = buffer.get('action')
    path = None
    if action not in list_special:
        if user_id and check_folder_clone(os.path.join('users', user_id)):
            path = os.path.join(get_pub_path(), 'clone', 'users', user_id)
        if sync_id and check_folder_clone(os.path.join(DIR_PROCESS, sync_id)):
            path = os.path.join(get_pub_path(), 'clone', DIR_PROCESS, sync_id)

        if path and to_decimal(os.path.getctime(path)) < to_decimal(get_config_ini('local', 'time_clone', 1589795205)):
            old_path = path + '_v30'
            os.rename(path, old_path)
            clone_code_for_migration_id(sync_id)
            folder_clear = '/sync/models/cart'
            shutil.rmtree(path + folder_clear)
            shutil.copytree(old_path + folder_clear, path + folder_clear)

    if not path:
        path = get_root_path()
    if wait:
        proc = subprocess.Popen(['python', path + '/bootstrap.py',
                                json_encode(buffer)], stdout=subprocess.PIPE, bufsize=1)
        data = ''
        while True:
            line = proc.stdout.readline().decode('utf8')
            if line != '':
                data += line
            else:
                break
        data = data.splitlines()
        if data:
            data = data[-1]
        decode_data = json_decode(data)
        if isinstance(decode_data, dict):
            return Prodict(**decode_data)
        return decode_data
    else:
        subprocess.Popen(
            ['python', path + '/bootstrap.py', json_encode(buffer)])


def start_autotest(auto_test_id):
    dir_test = 'test/' + str(auto_test_id)
    if auto_test_id and check_folder_clone(dir_test):
        path = get_pub_path() + '/' + DIR_PROCESS + dir_test
    else:
        path = get_root_path()
    buffer = {
        'auto_test_id': auto_test_id
    }
    subprocess.Popen(['python3', path + '/autotest.py', json_encode(buffer)])


def check_folder_clone(prefix):
    path = get_pub_path()
    if not isinstance(prefix, str):
        prefix = str(prefix)
    base_dir = os.path.join(path, 'clone', prefix)
    if not os.path.isdir(base_dir):
        return False
    folder_check = ['controllers', 'libs', 'models']
    file_check = ['bootstrap.py']
    for folder in folder_check:
        if not os.path.isdir(base_dir + '/' + BASE_DIR + '/' + folder):
            return False
    for file in file_check:
        if not os.path.isfile(base_dir + '/' + file):
            return False
    return True


def clear_folder_clone(migration_id):
    path = get_pub_path()
    if not isinstance(migration_id, str):
        migration_id = str(migration_id)
    base_dir = path + '/' + DIR_PROCESS + str(migration_id)
    if not os.path.isdir(base_dir):
        return True
    shutil.rmtree(base_dir)
    return True


def response_from_subprocess(data, conn=True):
    if conn:
        if isinstance(data, list) or isinstance(data, dict):
            data = json_encode(data)
        print(data, end='')
        sys.exit(1)
    return data


def get_config_ini(section, key=None, default=None, migration_id=None, file='config.ini'):
    config_file = os.path.join(get_pub_path(), '..', 'etc', file)
    if os.path.isfile(config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        try:
            if not key:
                return config[section]
            value = config[section][key]
            return value
        except Exception as e:
            return default
    return default


def parse_version(str_version):
    return version.parse(str_version)


def get_content_log_file(migration_id, path_file='exceptions_top', is_limit=True, limit_line=None):
    if migration_id:
        log_file = get_pub_path() + '/log/' + to_str(migration_id) + \
            '/' + path_file + '.log'
    else:
        log_file = get_pub_path() + '/log/' + path_file + '.log'
    lines = list()
    _limit = to_int(limit_line if limit_line else LIMIT_LINE_ERROR)
    if os.path.isfile(log_file):
        file_handle = open(log_file, "r")
        line_lists = file_handle.readlines()
        file_handle.close()
        if (not is_limit) or (to_len(line_lists) <= _limit):
            lines = line_lists
        else:
            index = 0 - _limit
            while index <= -1:
                lines.append(line_lists[index])
                index += 1
    return lines


def update_nested_dict(d, u):
    import collections.abc
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_nested_dict(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def url_to_link(url, link=None, target='_blank'):
    if not url:
        return ''
    if not link:
        link = url
    return "<a href='{}' target='{}'>{}</a>".format(url, target, link)


def get_random_useragent():
    user_agent = '''
		Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/525.19 (KHTML, like Gecko) Chrome/1.0.154.53 Safari/525.19

		Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/525.19 (KHTML, like Gecko) Chrome/1.0.154.36 Safari/525.19

		Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.10 (KHTML, like Gecko) Chrome/7.0.540.0 Safari/534.10

		Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US) AppleWebKit/534.4 (KHTML, like Gecko) Chrome/6.0.481.0 Safari/534.4

		Mozilla/5.0 (Macintosh; U; Intel Mac OS X; en-US) AppleWebKit/533.4 (KHTML, like Gecko) Chrome/5.0.375.86 Safari/533.4

		Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/532.2 (KHTML, like Gecko) Chrome/4.0.223.3 Safari/532.2

		Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/4.0.201.1 Safari/532.0

		Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/3.0.195.27 Safari/532.0

		Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/530.5 (KHTML, like Gecko) Chrome/2.0.173.1 Safari/530.5

		Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US) AppleWebKit/534.10 (KHTML, like Gecko) Chrome/8.0.558.0 Safari/534.10

		Mozilla/5.0 (X11; U; Linux x86_64; en-US) AppleWebKit/540.0 (KHTML,like Gecko) Chrome/9.1.0.0 Safari/540.0

		Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.14 (KHTML, like Gecko) Chrome/9.0.600.0 Safari/534.14

		Mozilla/5.0 (X11; U; Windows NT 6; en-US) AppleWebKit/534.12 (KHTML, like Gecko) Chrome/9.0.587.0 Safari/534.12

		Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.13 (KHTML, like Gecko) Chrome/9.0.597.0 Safari/534.13

		Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.11 Safari/534.16

		Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/534.20 (KHTML, like Gecko) Chrome/11.0.672.2 Safari/534.20

		Mozilla/5.0 (Windows NT 6.0) AppleWebKit/535.1 (KHTML, like Gecko) Chrome/14.0.792.0 Safari/535.1

		Mozilla/5.0 (Windows NT 5.1) AppleWebKit/535.2 (KHTML, like Gecko) Chrome/15.0.872.0 Safari/535.2

		Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.7 (KHTML, like Gecko) Chrome/16.0.912.36 Safari/535.7

		Mozilla/5.0 (Windows NT 6.0; WOW64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.66 Safari/535.11

		Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.45 Safari/535.19

		Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/535.24 (KHTML, like Gecko) Chrome/19.0.1055.1 Safari/535.24

		Mozilla/5.0 (Windows NT 6.2) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1090.0 Safari/536.6

		Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1

		Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.15 (KHTML, like Gecko) Chrome/24.0.1295.0 Safari/537.15

		Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36

		Mozilla/5.0 (Windows NT 6.2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1467.0 Safari/537.36

		Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36

		Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1623.0 Safari/537.36

		Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.116 Safari/537.36

		Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.103 Safari/537.36

		Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.38 Safari/537.36

		Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.71 Safari/537.36

		Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36

		Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36

		Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36

		Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.5; en-US; rv:1.9.1b3) Gecko/20090305 Firefox/3.1b3 GTB5

		Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.5; ko; rv:1.9.1b2) Gecko/20081201 Firefox/3.1b2

		Mozilla/5.0 (X11; U; SunOS sun4u; en-US; rv:1.9b5) Gecko/2008032620 Firefox/3.0b5

		Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.8.1.12) Gecko/20080214 Firefox/2.0.0.12

		Mozilla/5.0 (Windows; U; Windows NT 5.1; cs; rv:1.9.0.8) Gecko/2009032609 Firefox/3.0.8

		Mozilla/5.0 (X11; U; OpenBSD i386; en-US; rv:1.8.0.5) Gecko/20060819 Firefox/1.5.0.5

		Mozilla/5.0 (Windows; U; Windows NT 5.0; es-ES; rv:1.8.0.3) Gecko/20060426 Firefox/1.5.0.3

		Mozilla/5.0 (Windows; U; WinNT4.0; en-US; rv:1.7.9) Gecko/20050711 Firefox/1.0.5

		Mozilla/5.0 (Windows; Windows NT 6.1; rv:2.0b2) Gecko/20100720 Firefox/4.0b2

		Mozilla/5.0 (X11; Linux x86_64; rv:2.0b4) Gecko/20100818 Firefox/4.0b4

		Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2) Gecko/20100308 Ubuntu/10.04 (lucid) Firefox/3.6 GTB7.1

		Mozilla/5.0 (Windows NT 6.1; WOW64; rv:2.0b7) Gecko/20101111 Firefox/4.0b7

		Mozilla/5.0 (Windows NT 6.1; WOW64; rv:2.0b8pre) Gecko/20101114 Firefox/4.0b8pre

		Mozilla/5.0 (X11; Linux x86_64; rv:2.0b9pre) Gecko/20110111 Firefox/4.0b9pre

		Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:2.0b9pre) Gecko/20101228 Firefox/4.0b9pre

		Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:2.2a1pre) Gecko/20110324 Firefox/4.2a1pre

		Mozilla/5.0 (X11; U; Linux amd64; rv:5.0) Gecko/20100101 Firefox/5.0 (Debian)

		Mozilla/5.0 (Windows NT 6.1; WOW64; rv:6.0a2) Gecko/20110613 Firefox/6.0a2

		Mozilla/5.0 (X11; Linux i686 on x86_64; rv:12.0) Gecko/20100101 Firefox/12.0

		Mozilla/5.0 (Windows NT 6.1; rv:15.0) Gecko/20120716 Firefox/15.0a2

		Mozilla/5.0 (X11; Ubuntu; Linux armv7l; rv:17.0) Gecko/20100101 Firefox/17.0

		Mozilla/5.0 (Windows NT 6.1; rv:21.0) Gecko/20130328 Firefox/21.0

		Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:22.0) Gecko/20130328 Firefox/22.0

		Mozilla/5.0 (Windows NT 5.1; rv:25.0) Gecko/20100101 Firefox/25.0

		Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:25.0) Gecko/20100101 Firefox/25.0

		Mozilla/5.0 (Windows NT 6.1; rv:28.0) Gecko/20100101 Firefox/28.0

		Mozilla/5.0 (X11; Linux i686; rv:30.0) Gecko/20100101 Firefox/30.0

		Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0

		Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0

		Mozilla/5.0 (Windows NT 10.0; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0

		Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:58.0) Gecko/20100101 Firefox/58.0
		'''
    user_agent = user_agent.splitlines()
    user_agent = list(map(lambda x: to_str(x).strip('\t'), user_agent))
    user_agent = list(filter(lambda x: len(x) > 0, user_agent))
    return random.choice(user_agent)


def random_string(length=16, lower=False):
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    string = "".join(random.choice(chars) for _ in six.moves.xrange(length))
    return string if not lower else string.lower()


class StripHtml(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_html_tag(html, none_check=False):
    if not html:
        return ''
    s = StripHtml()
    s.feed(to_str(html))
    return s.get_data()


def get_jwt_token(data, private_key=None):
    if not private_key:
        private_key = get_config_ini('server', 'private_key')
    if not data.get('time'):
        data['time'] = to_str(to_int(time.time()))
    jwt_token = jwt.encode(data, private_key, algorithm='HS256')
    if isinstance(jwt_token, bytes):
        jwt_token = jwt_token.decode()
    return jwt_token


def get_api_server_url(path=None):
    api_url = get_config_ini('server', 'ngrok_url',
                             get_config_ini('server', 'api_url'))
    if to_str(path):
        api_url += '/' + to_str(path).strip('/')
    return api_url


def get_app_url(path=""):
    server_url = get_config_ini('server', 'app_url').strip('/')
    if path:
        server_url += "/" + path.strip('/')
    return server_url


def html_unescape(string):
    string = to_str(string)
    if not string:
        return ''
    return html.unescape(string)


def html_escape(string):
    string = to_str(string)
    if not string:
        return ''
    return html.escape(string)


def html_unquote(string):
    if not string:
        return ''
    return urllib.parse.unquote(string)


def is_local():
    return to_str(get_config_ini('local', 'mode', 'test')) == 'test' or to_bool(get_config_ini('local', 'is_local')) == True


def xml_to_dict(xml_data):
    try:
        data = xmltodict.parse(xml_data)
    except Exception:
        log_traceback()
        data = False
    return Prodict.from_dict(data)


def obj_to_list(obj):
    if not obj:
        return obj
    if not isinstance(obj, list):
        obj = [obj]
    return obj


def strip_none(data):
    if isinstance(data, dict):
        return {k: strip_none(v) for k, v in data.items() if k is not None and v is not None and not (isinstance(v, dict) and not v)}
    elif isinstance(data, list):
        return [strip_none(item) for item in data if item is not None]
    elif isinstance(data, tuple):
        return tuple(strip_none(item) for item in data if item is not None)
    elif isinstance(data, set):
        return {strip_none(item) for item in data if item is not None}
    else:
        return data


def get_flask_request_data():
    request_data = flask_request.data
    if isinstance(request_data, bytes):
        request_data = request_data.decode()
    request_data = json_decode(request_data)
    if not request_data:
        request_data = dict()
    return request_data


def is_uuid(string, uuid_version=4):
    try:
        uuid_obj = UUID(string, version=uuid_version)
    except ValueError:
        return False
    return str(uuid_obj) == string


def nl2br(string, is_xhtml=True):

    string = to_str(string)
    if not string:
        return ''
    if bool(BeautifulSoup(string, "html.parser").find()):
        return string
    if is_xhtml:
        return string.replace('\n', '<br />\n')
    else:
        return string.replace('\n', '<br>\n')


def rounding_price(rounding, price):
    price = to_decimal(price, 2)
    if rounding == 'nearest_099':
        price = to_int(price * 100)
        price = (price//100) * 100 + 100 - 1
        return to_decimal(price/100)
    if rounding == 'nearest_095':
        price = to_int(price * 100)
        residuals = price % 100
        if residuals > 95:
            price += 100
        price = (price // 100) * 100 + 100 - 5
        return to_decimal(price / 100)
    if rounding == 'nearest_1':
        return math.ceil(price)
    if rounding == 'nearest_10':
        price = math.ceil(price)
        residuals = price % 10
        if not residuals:
            return price
        return (price // 10) * 10 + 10
    if rounding == 'nearest_1099':
        price = math.floor(price)
        residuals = price % 10
        if residuals:
            price = (price // 10) * 10 + 10
        return price + 0.99
    return price


def get_server_id():
    return get_config_ini('server', 'id')
