from flask import Blueprint, request as flask_request, jsonify

from datasync.libs.utils import json_decode, start_subprocess

route_path = Blueprint('route_path', __name__)


# @route_path.route("action/<string:controller>/<string:action>", methods = ['post'])
# def controller_action(controller, action):
# 	request_data = flask_request.data
# 	if isinstance(request_data, bytes):
# 		request_data = request_data.decode()
# 	request_data = json_decode(request_data)
# 	if not request_data:
# 		request_data = dict()
# 	action = action.replace('-', '_')
# 	buffer = dict()
# 	buffer['controller'] = controller
# 	buffer['action'] = action
# 	buffer['data'] = request_data
# 	create = start_subprocess(buffer, wait = True)
# 	return jsonify(create)

@route_path.route("action/<string:controller>/<string:action>", methods = ['post'])
def user_controller_action(controller, action):
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	if not request_data:
		request_data = dict()
	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	action = action.replace('-', '_')
	buffer = dict()
	buffer['controller'] = controller
	buffer['action'] = action
	buffer['data'] = request_data
	create = start_subprocess(buffer, wait = True)
	return jsonify(create)