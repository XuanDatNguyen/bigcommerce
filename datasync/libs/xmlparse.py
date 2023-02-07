import re
from xml.etree.ElementTree import fromstring

from xmljson import badgerfish as bf

from datasync.libs.prodict import Prodict


class XMLParser:
	@staticmethod
	def remove_namespace(xml):
		"""
		Strips the namespace from XML document contained in a string.
		Returns the stripped string.

		Parameters:
			xml (str)
		"""
		regex = re.compile(' xmlns(:ns2)?="[^"]+"|(ns2:)|(xml:)')
		return regex.sub("", xml)


	@classmethod
	def parse_xml_to_dict(cls, xml):
		"""
		Parse XML string to a Prodict.
		Parameters:
			xml (str)
		"""
		if isinstance(xml, bytes):
			xml = xml.decode()
		result = xml
		try:
			xml = cls.remove_namespace(xml)
			data = bf.data(fromstring(xml))
			result = Prodict.from_dict(data)
		except Exception:
			pass
		return result
