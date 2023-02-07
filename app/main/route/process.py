import os
import subprocess

from flask import Blueprint, request as flask_request, jsonify

from datasync.libs.utils import json_decode, start_subprocess, response_success, clone_code_for_process
from datasync.libs.utils import response_error, get_pub_path, to_str, change_permissions_recursive, to_int, check_pid, clone_code_for_user

process_path = Blueprint('process_path', __name__)


@process_path.route("process/stop_pid/<int:pid>", methods = ['post'])
def stop_pid(pid):
	pid = to_int(pid)
	retry = 5
	while check_pid(pid) and retry > 0:
		subprocess.call(['kill', '-9', to_str(pid)])
		retry -= 1
	return jsonify(response_success())


@process_path.route("process/stop/<int:sync_id>", methods = ['post'])
def stop(sync_id):
	'''
		file: ../../../app/documents/docs/process/stop.yml
	'''
	buffer = dict()

	buffer['controller'] = 'process'
	buffer['action'] = 'stop_process'
	buffer['data'] = {'sync_id': sync_id}
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	if request_data and request_data.get('end_loop'):
		buffer['data']['end_loop'] = True
	stop_action = start_subprocess(buffer, True)
	return jsonify(stop_action)


@process_path.route("process/start/<int:sync_id>", methods = ['post'])
def start(sync_id):
	'''
		file: ../../../app/documents/docs/process/start.yml
	'''
	buffer = dict()

	buffer['controller'] = 'process'
	buffer['action'] = 'start'
	buffer['data'] = {'sync_id': sync_id}
	start_subprocess(buffer)
	return jsonify(response_success())
@process_path.route("process/refresh/<int:sync_id>", methods = ['post'])
def refresh(sync_id):
	'''
		file: ../../../app/documents/docs/process/start.yml
	'''
	buffer = dict()

	buffer['controller'] = 'process'
	buffer['action'] = 'refresh'
	buffer['data'] = {'sync_id': sync_id}
	start_subprocess(buffer)
	return jsonify(response_success())

@process_path.route("process/upload-file-custom/<int:sync_id>", methods = ['POST', 'OPTIONS'])
def upload_file_custom(sync_id):
	'''
		file: ../../../app/documents/docs/process/start.yml
	'''
	file = flask_request.files.get('file_custom')

	if not file:
		return jsonify(response_error())
	path_process = os.path.join(get_pub_path(), 'processes')
	if not os.path.isdir(path_process):
		os.makedirs(path_process, 0o777)
		change_permissions_recursive(path_process)
	path_upload = os.path.join(get_pub_path(), 'processes', to_str(sync_id), 'datasync', 'models', 'channels')
	if not os.path.isdir(path_upload):
		os.makedirs(path_upload, 0o777)
	file.save(os.path.join(path_upload, 'custom.py'))
	return jsonify(response_success())


@process_path.route("<string:entity>/clone/<int:entity_id>", methods = ['post'])
def clone(entity, entity_id):
	buffer = dict()
	if entity == 'process':
		clone_code_for_process(entity_id)
	elif entity == 'user':
		clone_code_for_user(entity_id)
	return jsonify(response_success())
