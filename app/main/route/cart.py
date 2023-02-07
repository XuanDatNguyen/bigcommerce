from flask import Blueprint, request as flask_request, jsonify

from datasync.libs.utils import json_decode, start_subprocess, get_flask_request_data

cart_path = Blueprint('cart_path', __name__)


@cart_path.route("<string:entity>/<action>", methods = ['post'])
def product_update(cart_type, entity, action):
	request_data = get_flask_request_data()
	request_data['process_type'] = entity
	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	buffer = dict()
	buffer['controller'] = cart_type
	buffer['action'] = f'{entity}_{action}'
	buffer['data'] = request_data
	create = start_subprocess(buffer, wait = False)
	return jsonify(create)
