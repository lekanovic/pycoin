from ..script import opcodes, tools
from ..script.microcode import VCH_TRUE

from ... import ecdsa
from ... import encoding

from ...networks import address_prefix_for_netcode
from ...serialize import b2h

from .ScriptType import ScriptType


# Check Asset transaction: http://coinsecrets.org/

class ScriptOPReturn(ScriptType):
	TEMPLATE = tools.compile("OP_RETURN")

	def __init__(self, msg):
		if len(msg) > 40:
			raise ValueError("Message can only be 40 bytes")
		self.msg = msg.encode("hex")
		self._script = None

	@classmethod
	def from_script(cls, script):
		r = cls.match(script)
		if r:
			msg = r["PUBKEY_LIST"][0]
			s = cls(msg)
			return s
		raise ValueError("bad script")

	def script(self):
		if self._script is None:
			# create the script
			# TEMPLATE = OP_RETURN msg
			script_source = "OP_RETURN %s" % (self.msg)
			print script_source
			self._script = tools.compile(script_source)
		return self._script

	def solve(self, **kwargs):
		return 0

	def __repr__(self):
		return "<Script: op_return %s>" % (self.msg)
