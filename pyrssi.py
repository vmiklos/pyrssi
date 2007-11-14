#!/usr/bin/env python

import cgitb, cgi, re, socket, os, time, Cookie, sha, sys, urllib, base64
from distutils import sysconfig
from config import config

cgitb.enable()
last = None

class Pyrssi:
	def __init__(self, sock_path, passwd):
		self.sock_path = sock_path
		self.passwd = passwd
		self.year = time.time() + 60*60*24*365
		self.dict = {}
	
	def cookie2dict(self):
		try:
			cookie = Cookie.SimpleCookie(os.environ["HTTP_COOKIE"])
			self.dict = eval(base64.decodestring(cookie['pyrssi'].value))
		except Exception:
			self.dict = {}

	def dict2cookie(self):
		cookie = Cookie.SimpleCookie()
		cookie['pyrssi'] = base64.encodestring(self.dict.__repr__()).replace('\n', '')
		cookie['pyrssi']['max-age'] = self.year
		print cookie

	def send(self, what):
		self.cookie2dict()
		if 'network' in self.dict.keys():
			self.network = self.dict['network']
		else:
			self.network = None
		if 'refnum' in self.dict.keys():
			self.refnum = self.dict['refnum']
		else:
			self.refnum = None
		if 'channel' in self.dict.keys():
			self.channel = self.dict['channel']
		else:
			self.channel = None
		if isinstance(what, cgi.FieldStorage):
			self.form = what
			try:
				data = []
				if "msg_prefix" in self.form.keys():
					data.append(self.form['msg_prefix'].value)
				data.append(self.form['msg'].value)
				self.__send("".join(data))
			except KeyError:
				pass
		else:
			self.__send(what)

	def receive(self):
		self.__handlecookies()
		self.__dumpheader()
		if "pass" not in self.dict.keys():
			self.__dumplogin()
		elif "channel" not in self.dict.keys():
			self.__dumpwindowlist()
			self.__sysinfo()
		else:
			self.__dumpform()
			self.__dumplastlines()
		if "pass" in self.dict.keys():
			self.__dumplogout()
		self.__dumpfooter()

	def __sysinfo(self):
		print "Powered by Python %s (on %s/%s)" % (sysconfig.get_python_version(), sys.platform, os.name)
		print "<br />"

	def __handlecookies(self):
		# see if we should set cookies
		if "action" in self.form.keys() and self.form['action'].value == "login":
			if sha.sha(self.form['pass'].value).hexdigest() != self.passwd:
				self.__dumpheader()
				self.__dumplogin("wrong password!<br />")
				self.__dumpfooter()
				sys.exit(0)
			self.dict = {}
			self.dict['pass'] = self.form['pass'].value
			self.dict2cookie()

		if "action" in self.form.keys() and self.form['action'].value == "logout":
			self.dict = {}
			self.dict2cookie()

		if "action" in self.form.keys() and self.form['action'].value == "windowselect":
			self.dict['channel'] = self.form['window'].value.lower()
			self.dict['network'] = self.form['network'].value
			self.dict['refnum'] = self.form['refnum'].value
			self.dict2cookie()
			self.channel = self.form['window'].value.lower()
			self.network = self.form['network'].value
			self.refnum = self.form['refnum'].value

		if "action" in self.form.keys() and self.form['action'].value == "windowlist":
			if 'channel' in self.dict.keys():
				del self.dict['channel']
				self.dict2cookie()

	def __connect(self):
		self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		self.sock.connect(self.sock_path)

	def __send(self, what):
		def go(what):
			for i in self.__recv("windowlist").split("\n"):
				refnum = re.sub(r'(.*): .*', r'\1', i)
				window = re.sub(r'.*: (.*) \(.*', r'\1', i)
				network = re.sub(r'.* \((.*)\).*', r'\1', i)
				if refnum == what[3:] or window.lower() == what[3:].lower():
					self.dict['channel'] = window.lower()
					self.dict['network'] = network
					self.dict['refnum'] = refnum
					self.dict2cookie()
					self.channel = window
					self.network = network.lower()
					self.refnum = refnum
					break
		ret = 0
		if len(what):
			if what.lower().startswith("/g "):
				go(what)
			elif what.lower().startswith("/q "):
				self.__connect()
				ret += self.sock.send("send %s" % what)
				time.sleep(0.5)
				self.__connect()
				go(what)
			else:
				self.__connect()
				ret += self.sock.send("switch %s" % self.refnum)
				self.__connect()
				ret += self.sock.send("send %s" % what)
				time.sleep(0.5)
		return ret

	def __recv(self, what):
		ret = []
		self.__connect()
		self.sock.send(what)
		while True:
			buf = self.sock.recv(4096)
			if not buf:
				break
			ret.append(buf)
		return "".join(ret)

	def __getlastlines(self):
		ret = []
		buf = self.__recv("get_lines %s" % self.refnum)
		return buf.split("\n")[-25:]

	def __dumpheader(self):
		print "Content-Type: text/vnd.wap.wml"
		print "Cache-Control: no-cache, must-revalidate"
		print "Pragma: no-cache"
		print
		sys.stdout.write("""<?xml version="1.0"?>
		<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN"
		"http://www.wapforum.org/DTD/wml_1.1.xml">
		<wml><card id="XML" title=\"%s""" % time.strftime("[%H:%M]"))
		if 'channel' in self.dict.keys():
			sys.stdout.write(" %s" % self.dict['channel'])
		print """\"><p>"""

	def __dumplogin(self, errmsg=""):
		print """
		%s
		password: <input type="password" name="pass" value="" /><br/>
		<anchor>[login]
		<go method="post" href="pyrssi.py">
		<postfield name="pass" value="$(pass)"/>
		<postfield name="action" value="login"/>
		</go>
		</anchor>""" % errmsg

	def __getwindowlist(self):
		ret = self.__recv("windowlist").split("\n")
		ret.insert(0, '1: (status) (notconnected)')
		return ret

	def __escape(self, s):
		return cgi.escape(s).replace("$", "$$")

	def __dumpwindowlist(self):
		# how many channels do we want in a page?
		cn = 10
		page = 0
		jumponly = False
		if "page" in self.form.keys():
			page = int(self.form['page'].value)
		if "jumponly" in self.form.keys():
			jumponly = bool(self.form['jumponly'].value)
		if jumponly:
			print """<input type="text" name="msg" value="" /><br/>
			<anchor>[go]
			<go method="post" href="pyrssi.py">
			<postfield name="msg_prefix" value="/g "/>
			<postfield name="msg" value="$(msg)"/>
			<postfield name="action" value="msg"/>
			</go>
			</anchor>
			<br />"""
			return
		print """<a href="pyrssi.py?action=windowlist&amp;jumponly=True">[quick jump]</a><br />"""
		for i in self.__getwindowlist():
			refnum = re.sub(r'(.*): .*', r'\1', i)
			if int(refnum)+1 == (page*cn):
				print """<a href="pyrssi.py?page=%d">[previous]</a><br />""" % (page-1)
			elif int(refnum) >= (page*cn) and int(refnum) < (page*cn+cn):
				window = re.sub(r'.*: (.*) \(.*', r'\1', i)
				if not len(window):
					window = "(disconnected)"
				network = re.sub(r'.* \((.*)\).*', r'\1', i)
				if not len(network):
					network = "notconnected"
				print """<a href="pyrssi.py?action=windowselect&amp;refnum=%s&amp;window=%s&amp;network=%s">%s</a><br />""" % (refnum, urllib.pathname2url(window), network, self.__escape(window))
			elif int(refnum) == (page*cn+cn):
				print """<a href="pyrssi.py?page=%d">[next]</a><br />""" % (page+1)
	def __dumpform(self):
		print """<input type="text" name="msg" value="" /><br/>
		<anchor>[send]
		<go method="post" href="pyrssi.py">
		<postfield name="msg" value="$(msg)"/>
		<postfield name="action" value="msg"/>
		</go>
		</anchor>"""
		print """
		<anchor>[windowlist]
		<go method="post" href="pyrssi.py">
		<postfield name="action" value="windowlist"/>
		</go>
		</anchor>"""
	def __dumplogout(self):
		print """
		<anchor>[logout]
		<go method="post" href="pyrssi.py">
		<postfield name="action" value="logout"/>
		</go>
		</anchor>
		<br />"""

	def __dumpfooter(self):
		print """</p>
		</card>
		</wml>"""

	def __dumplastlines(self):
		self.lastlines = self.__getlastlines()
		self.lastlines.reverse()
		for i in self.lastlines:
			print self.__escape(i),  '<br />'

pyrssi = Pyrssi(config.socket, config.password)
pyrssi.send(cgi.FieldStorage())
pyrssi.receive()
