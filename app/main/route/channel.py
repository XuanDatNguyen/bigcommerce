from flask import Blueprint, request as flask_request, jsonify

from datasync.libs.utils import json_decode, start_subprocess, response_success, get_flask_request_data, response_error

channel_path = Blueprint('channel_path', __name__)


@channel_path.route("channel/setup", methods=['post'])
def setup():
    '''
    file: ../../../app/documents/docs/channel/setup.yml
    '''
    request_data = get_flask_request_data()

    buffer = dict()
    buffer['controller'] = 'channel'
    buffer['action'] = 'setup'
    buffer['data'] = request_data
    setup = start_subprocess(buffer, wait=True)

    return jsonify(setup.to_dict())


@channel_path.route("channel/pull/<int:sync_id>", methods=['post'])
def pull(sync_id):
    '''
    file: ../../../app/documents/docs/channel/pull.yml
    '''
    request_data = get_flask_request_data()


    buffer = dict()
    buffer['controller'] = 'channel'
    buffer['action'] = 'restart_pull'
    buffer['data'] = {'sync_id': sync_id}
    buffer['data'].update(request_data)

    start_subprocess(buffer)

    return jsonify(response_success())


@channel_path.route("channel/push/<int:sync_id>", methods=['post'])
def push(sync_id):
    '''
    file: ../../../app/documents/docs/channel/push.yml
    '''
    request_data = get_flask_request_data()

    request_data['sync_id'] = sync_id
    request_data['is_push_action'] = True
    buffer = dict()
    buffer['controller'] = 'channel'
    buffer['action'] = 'restart_push'
    buffer['data'] = request_data
    start_subprocess(buffer)

    return jsonify(response_success())


@channel_path.route("channel/assign-template/<int:sync_id>", methods=['post'])
def assign_template(sync_id):
    '''
    file: ../../../app/documents/docs/channel/push.yml
    '''
    request_data = get_flask_request_data()

    request_data['sync_id'] = sync_id
    request_data['warehouse_action'] = 'assign_template'
    buffer = dict()
    buffer['controller'] = 'channel'
    buffer['action'] = 'restart_push'
    buffer['data'] = request_data
    start_subprocess(buffer)

    return jsonify(response_success())


@channel_path.route("channel/verify_connection/<int:sync_id>", methods=['post'])
def verify_connection(sync_id):
    request_data = get_flask_request_data()

    request_data['sync_id'] = sync_id
    buffer = dict()
    buffer['controller'] = 'channel'
    buffer['action'] = 'verify_connection'
    buffer['data'] = request_data
    verify = start_subprocess(buffer, wait=True)
    return jsonify(verify.to_dict())


@channel_path.route("channel/<int:channel_id>/create-inventory-process", methods=['post'])
def create_inventory_process(channel_id):
    data = {
        'channel_id': channel_id
    }
    buffer = dict()
    buffer['controller'] = 'product'
    buffer['action'] = 'create_inventory_process'
    buffer['data'] = data
    create = start_subprocess(buffer, wait=True)
    return jsonify(create)


@channel_path.route("channel/<int:channel_id>/products/bulk-delete", methods=['post'])
def bulk_delete_product_channel(channel_id):
    request_data = get_flask_request_data()
    if not request_data.get('product_ids'):
        return jsonify(response_error('Data invalid'))
    request_data['channel_id'] = channel_id
    buffer = dict()
    buffer['controller'] = 'channel'
    buffer['action'] = 'bulk_delete_product'
    buffer['data'] = request_data
    create = start_subprocess(buffer, wait=True)
    return jsonify(create)


@channel_path.route("channel/<int:channel_id>/products/<string:product_id>", methods=['delete'])
def delete_product_channel(channel_id, product_id):
    data = {
        'channel_id': channel_id,
        'product_id': product_id
    }
    buffer = dict()
    buffer['controller'] = 'channel'
    buffer['action'] = 'delete_product'
    buffer['data'] = data
    create = start_subprocess(buffer, wait=True)
    return jsonify(create)


@channel_path.route("channel/<int:channel_id>/<string:action>", methods=['post'])
def channel_action(channel_id, action):
    request_data = flask_request.data
    if isinstance(request_data, bytes):
        request_data = request_data.decode()
    request_data = json_decode(request_data)
    if not request_data:
        request_data = dict()
    request_data['channel_id'] = channel_id
    action = action.replace('-', '_')
    request_data['action'] = action
    buffer = dict()
    buffer['controller'] = 'channel'
    buffer['action'] = 'channel_action'
    buffer['data'] = request_data
    start_subprocess(buffer)
    return jsonify(response_success())
