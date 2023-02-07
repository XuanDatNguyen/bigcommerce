from flask import Blueprint, request as flask_request, jsonify

from datasync.libs.utils import json_decode, start_subprocess, response_success

server_path = Blueprint('server_path', __name__)


@server_path.route("server/status", methods = ['get'])
def status():
	"""
		file: ../../../app/documents/docs/process/stop.yml
	"""
	buffer = dict()

	buffer['controller'] = 'server'
	buffer['action'] = 'get_server_status'
	buffer['data'] = dict()
	server_status = start_subprocess(buffer, True)
	return jsonify(server_status)
