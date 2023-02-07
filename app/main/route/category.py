from flask import Blueprint, request as flask_request, jsonify

from datasync.libs.utils import json_decode, start_subprocess

category_path = Blueprint('category_path', __name__)


@category_path.route("category", methods = ['post'])
def add():
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	# user_id = Authorization().get_user_id_from_headers(flask_request)

	buffer = dict()
	buffer['controller'] = 'category'
	buffer['action'] = 'create'
	buffer['data'] = request_data
	category = start_subprocess(buffer, wait = True)
	return jsonify(category)
