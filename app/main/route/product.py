from flask import Blueprint, request as flask_request, jsonify

from datasync.libs.utils import json_decode, start_subprocess, response_success, response_error, get_flask_request_data

product_path = Blueprint('product_path', __name__)


@product_path.route("product/<string:process_type>/<int:sync_id>", methods = ['post'])
def update(process_type, sync_id):
	'''
	file: ../../../app/documents/docs/channel/push.yml
	'''
	request_data = get_flask_request_data()

	request_data['sync_id'] = sync_id
	buffer = dict()
	buffer['controller'] = 'channel'
	buffer['action'] = f'start_{process_type}'
	buffer['data'] = request_data
	start_subprocess(buffer)

	return jsonify(response_success())


@product_path.route("template/update/<int:sync_id>", methods = ['post'])
def template_update(sync_id):
	'''
	file: ../../../app/documents/docs/channel/push.yml
	'''
	request_data = get_flask_request_data()

	request_data['sync_id'] = sync_id
	buffer = dict()
	buffer['controller'] = 'channel'
	buffer['action'] = 'start_template_update'
	buffer['data'] = request_data
	start_subprocess(buffer)

	return jsonify(response_success())


@product_path.route("product/edit/<string:product_id>", methods = ['put'])
def edit(product_id):
	'''
	file: ../../../app/documents/docs/product/edit.yml
	'''
	request_data = get_flask_request_data()

	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	request_data['product_id'] = product_id
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'edit'
	buffer['data'] = request_data
	setup = start_subprocess(buffer, wait = True)
	return jsonify(setup.to_dict())


@product_path.route("product/delete/<string:product_id>", methods = ['post'])
def delete(product_id):
	'''
	file: ../../../app/documents/docs/product/delete.yml
	'''
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'start_pull'
	buffer['data'] = {'sync_id': sync_id}
	start_subprocess(buffer)
	# if setup.result == Response.SUCCESS:
	# 	buffer = dict()
	# 	buffer['controller'] = 'product'
	# 	buffer['action'] = 'start'
	# 	buffer['data'] = request_data
	# 	start_subprocess(buffer)

	return jsonify(response_success())


@product_path.route("product", methods = ['post'])
def add():
	request_data = get_flask_request_data()

	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'create'
	buffer['data'] = request_data
	product = start_subprocess(buffer, wait = True)
	return jsonify(product)


@product_path.route("product/export", methods = ['post'])
def export():
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'export'
	buffer['data'] = get_flask_request_data()
	start_subprocess(buffer)
	return jsonify(response_success())


@product_path.route("channel/<int:channel_id>/product/listing", methods = ['post'])
def listing(channel_id):
	'''
	file: ../../../app/documents/docs/product/edit.yml
	'''
	request_data = get_flask_request_data()

	if not request_data or not isinstance(request_data, dict) or not request_data.get('product_ids'):
		return jsonify(response_error("data invalid"))
	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	request_data['channel_id'] = channel_id
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'listing'
	buffer['data'] = request_data
	setup = start_subprocess(buffer, wait = True)
	return jsonify(setup.to_dict())


@product_path.route("product/csv-file-sample", methods = ['post'])
def product_csv_file_sample():
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'product_csv_file_sample'
	buffer['data'] = dict()
	title = start_subprocess(buffer, wait = True)
	return jsonify(title)


@product_path.route("/product/import/csv", methods = ['post'])
def product_import_csv():
	request_data = get_flask_request_data()

	if not request_data or not isinstance(request_data, dict) or not request_data.get('file_url'):
		return jsonify(response_error('Data invalid'))
	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'csv_import'
	buffer['data'] = request_data
	start_subprocess(buffer)
	return jsonify(response_success())


@product_path.route("/product/bulk-edit", methods = ['post'])
def bulk_edit_product():
	request_data = get_flask_request_data()

	if not request_data or not isinstance(request_data, dict) or not request_data.get('file_url'):
		return jsonify(response_error('Data invalid'))
	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	buffer = dict()
	buffer['controller'] = 'channel'
	buffer['action'] = 'bulk_edit_product'
	buffer['data'] = request_data
	start_subprocess(buffer)
	return jsonify(response_success())


@product_path.route("/inventory/csv-file-sample", methods = ['post'])
def inventory_csv_file_sample():
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'inventory_csv_file_sample'
	buffer['data'] = dict()
	title = start_subprocess(buffer, wait = True)
	return jsonify(title)


@product_path.route("inventory/import/csv", methods = ['post'])
def inventories_import():
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	if not request_data or not isinstance(request_data, dict) or not request_data.get('file_url'):
		return jsonify(response_error('Data invalid'))
	# request_data['user_id'] = Authorization().get_user_id_from_headers(flask_request)
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'inventories_import'
	buffer['data'] = request_data
	start_subprocess(buffer)
	return jsonify(response_success())


@product_path.route("inventory/export", methods = ['post'])
def inventories_export():
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	if not request_data or not isinstance(request_data, dict) or request_data.get('location_id') is None:
		return jsonify(response_error('Data invalid'))
	buffer = dict()
	buffer['controller'] = 'product'
	buffer['action'] = 'inventories_export'
	buffer['data'] = {
		'location_id': request_data.get('location_id')
	}
	start_subprocess(buffer)
	return jsonify(response_success())


@product_path.route("product/refresh/<int:sync_id>/<string:product_id>", methods = ['put'])
def refresh(sync_id, product_id):
	'''
	file: ../../../app/documents/docs/channel/push.yml
	'''
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	if not request_data:
		request_data = dict()
	request_data['sync_id'] = sync_id
	request_data['product_id'] = product_id
	buffer = dict()
	buffer['controller'] = 'channel'
	buffer['action'] = 'start_refresh_product'
	buffer['data'] = request_data
	start_subprocess(buffer, wait = True)
	return jsonify(response_success())


@product_path.route("channel/<int:sync_id>/product/refresh", methods = ['post'])
def refresh_list_product(sync_id):
	'''
	file: ../../../app/documents/docs/channel/push.yml
	'''
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	if not request_data:
		request_data = dict()
	request_data['sync_id'] = sync_id
	buffer = dict()
	buffer['controller'] = 'channel'
	buffer['action'] = 'start_refresh_list_product'
	buffer['data'] = request_data
	start_subprocess(buffer, wait = False)
	return jsonify(response_success())