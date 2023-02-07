from flask import Blueprint, current_app, jsonify, request as flask_request

from datasync.libs.utils import start_subprocess, response_success, json_decode, response_error, get_flask_request_data

cron_path = Blueprint('cron_path', __name__)


# @cron_path.route('/scheduler/<string:cron_id>', methods = ['post'])
def schedule(cron_id):
	request_data = flask_request.data
	if isinstance(request_data, bytes):
		request_data = request_data.decode()
	request_data = json_decode(request_data)
	if not request_data.get('user_id') or not request_data.get('process_id'):
		return jsonify(response_error('Data invalid'))
	user_id = request_data['user_id']
	process_id = request_data['process_id']
	interval = request_data.get('interval', {"minutes": 10})
	current_app.apscheduler.add_job(func = scheduled_task, trigger = "interval", id = cron_id, args = (user_id, cron_id, process_id), **interval)
	# scheduled_task(user_id, cron_id, process_id)
	return jsonify(response_success())


@cron_path.route('/scheduler/<string:cron_id>', methods = ['get'])
def schedule_details(cron_id):
	job = current_app.apscheduler.get_job(cron_id)
	if not job:
		return jsonify(response_error())
	return jsonify(response_success(job.next_run_time.strftime("%Y-%m-%d, %H:%M:%S")))


@cron_path.route('/scheduler/<string:cron_id>', methods = ['delete'])
def delete_tasks(cron_id):
	try:
		current_app.apscheduler.remove_job(id = cron_id)
	except:
		pass
	return jsonify(response_success())


@cron_path.route('/scheduler/<string:process_id>', methods = ['post'])
def scheduled_task(process_id):
	request_data = get_flask_request_data()

	buffer = dict()
	buffer['controller'] = 'scheduler'
	buffer['action'] = 'scheduler'
	buffer['data'] = {
		'sync_id': process_id,
	}
	buffer['data'].update(request_data)
	start_subprocess(buffer)
	return "Scheduled several long running tasks."
