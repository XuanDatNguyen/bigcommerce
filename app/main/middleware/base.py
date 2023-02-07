from datasync.libs.response import Response


class MiddlewareBase:
	MSG = ''


	def __init__(self, environ, **kwargs):
		self.environ = environ


	def execute(self):
		handle = self.handle()
		if not handle:
			return Response().error(self.MSG)
		return Response().success()


	def handle(self):
		return False
