from datasync.libs.utils import *
try:
    buffer = sys.argv[1]
    buffer = json.loads(buffer)
except:
    sys.exit()
controller_name = buffer.get('controller', 'migration')
action_name = buffer.get('action')
data = buffer.get('data')
if not action_name:
    sys.exit()
if not controller_name:
    controller_name = 'migration'
controller = get_controller(controller_name, data)
try:
    getattr(controller, 'execute')(action_name, data)
except Exception as e:
    error = traceback.format_exc()
    prefix = ""
    if data:
        if data.get('user_id'):
            prefix = to_str(data['user_id'])
        if data.get("sync_id"):
            prefix = os.path.join(prefix, to_str(data['sync_id']))
    log(error, prefix)
os.kill(os.getpid(), 9)
