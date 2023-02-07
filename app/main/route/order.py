from flask import Blueprint, request as flask_request, jsonify

from datasync.libs.utils import json_decode, start_subprocess, response_success

order_path = Blueprint('order_path', __name__)


@order_path.route("order/process/<int:channel_id>", methods = ['post'])
def create_order_process(channel_id):
	data = {
		'channel_id': channel_id
	}
	buffer = dict()
	buffer['controller'] = 'order'
	buffer['action'] = 'create_order_process'
	buffer['data'] = data
	create = start_subprocess(buffer, wait = True)
	return jsonify(create)


@order_path.route("order", methods = ['post'])
def add():
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	buffer = dict()
	buffer['controller'] = 'order'
	buffer['action'] = 'create'
	buffer['data'] = request_data
	order = start_subprocess(buffer, wait = True)
	return jsonify(order)


@order_path.route("order", methods = ['put'])
def update():
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	buffer = dict()
	buffer['controller'] = 'order'
	buffer['action'] = 'update'
	buffer['data'] = request_data
	start_subprocess(buffer)
	return jsonify(response_success())


@order_path.route("order/export", methods = ['post'])
def export():
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)

	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	buffer = dict()
	buffer['controller'] = 'order'
	buffer['action'] = 'export'
	buffer['data'] = request_data
	start_subprocess(buffer)
	return jsonify(response_success())


@order_path.route("order/sync/<string:order_id>", methods = ['put'])
def sync(order_id):
	'''
	file: ../../../app/documents/docs/channel/push.yml
	'''
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	if not request_data:
		request_data = dict()
	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	request_data['order_id'] = order_id
	request_data['process_type'] = 'order'
	buffer = dict()
	buffer['controller'] = 'channel'
	buffer['action'] = 'sync_order'
	buffer['data'] = request_data
	start_subprocess(buffer, wait = True)
	return jsonify(response_success())
