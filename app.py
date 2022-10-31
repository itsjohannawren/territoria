#!/usr/bin/env bash
"""" &>/dev/null
	__DIR__="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P 2>/dev/null)"
	if [ -z "${__DIR__}" ]; then
		echo "Error: Failed to determine directory containing this script" 1>&2
		exit 1
	fi

	while [ "${__DIR__}" != "/" ]; do
		if [ -f "${__DIR__}/pyvenv.cfg" ] && [ -f "${__DIR__}/bin/activate" ] && [ -h "${__DIR__}/bin/python" ]; then
			exec "${__DIR__}/bin/python" "${0}" "${@}"
		fi
		__DIR__="$(dirname "${DIR}")"
	done

	if command -v python3 &>/dev/null; then
		exec python3 "${0}" "${@}"
	fi

	exec python "${0}" "${@}"
# """
# ==============================================================================

import datetime
import json
import signal
import time

from croniter import croniter
from icecream import ic

# ==============================================================================

def ansiColorParse (data:str, foreground = True) -> str:
	vga_map = {
		"black": 30,
		"red": 31,
		"green": 32,
		"yellow": 33,
		"blue": 34,
		"magenta": 35,
		"cyan": 36,
		"white": 37
	}

	if data.lower () in vga_map:
		if foreground == True:
			return str (vga_map [data.lower ()])
		else:
			return str (vga_map [data.lower ()] + 10)

	if re.search (r"^(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9]|[0-9])$", data) is not None:
		return "5;" + data

	components = re.search (r"(?i)^#?(?P<red>[0-9a-f]{2})(?P<green>[0-9a-f]{2})(?P<blue>[0-9a-f]{2})$", data)
	if components is not None:
		return "2;%i;%i;%i" % (
			int (components ["red"], base = 16),
			int (components ["green"], base = 16),
			int (components ["blue"], base = 16)
		)

	return None

def ansiColor (
	reset:bool = False,
	bright:bool = False,
	faint:bool = False,
	italic:bool = False,
	underline:bool = False,
	blink:bool = False,
	strikeout:bool = False,
	double_underline:bool = False,
	framed:bool = False,
	encircled:bool = False,
	overlined:bool = False,

	foreground:str = None,
	background:str = None,
) -> str:
	codes = []

	if reset == True:
		codes.append ("0")
	if bright == True:
		codes.append ("1")
	if faint == True:
		codes.append ("2")
	if italic == True:
		codes.append ("3")
	if underline == True:
		codes.append ("4")
	if blink == True:
		codes.append ("5")
	if strikeout == True:
		codes.append ("9")
	if double_underline == True:
		codes.append ("21")
	if framed == True:
		codes.append ("51")
	if encircled == True:
		codes.append ("52")
	if overlined == True:
		codes.append ("53")

	if foreground is not None:
		fg = ansiColorParse (foreground)
		if fg is not None:
			codes.append (fg)

	if background is not None:
		bg = ansiColorParse (background, foreground = False)
		if bg is not None:
			codes.append (bg)

	return "\x1b[" + ";".join (codes) + "m"

# ==============================================================================

INDENT = 0
INDENT_STRING = "   "

def indent ():
	INDENT = INDENT + 1

def outdent ():
	INDENT = INDENT - 1
	if INDENT < 0:
		INDENT = 0

def wrapOutput (string:str, color:bool = True):
	lines = string.split ("\n")
	for line in lines:
		if color == True:
			print ("%s%7s%s | %s%s%s" % (ansiColor (reset = True), "", ansiColor (bright = True, foreground = "white"), ansiColor (reset = True), INDENT_STRING * INDENT, line))
		else:
			print ("%7s | %s%s" % ("", INDENT_STRING * INDENT, line))

def message (prefix:str, string:str, prefix_ansi:str = None, color:bool = True):
	_prefix = prefix [0:7]
	first = True
	lines = string.split ("\n")
	for line in lines:
		if first == True:
			first = False
			if color == True and prefix_ansi is not None:
				print ("%s%7s%s | %s%s%s" % (prefix_ansi, _prefix, ansiColor (reset = True, bright = True, foreground = "white"), INDENT_STRING * INDENT, line, ansiColor (reset = True)))
			else:
				print ("%7s | %s%s" % (_prefix, INDENT_STRING * INDENT, line))
		else:
			print ("%7s | %s%s" % ("", INDENT_STRING * INDENT, line))

def debug (string:str, color:bool = True):
	message ("Debug", string, ansiColor (reset = True, bright = True, foreground = "cyan"), color)

def info (string:str, color:bool = True):
	message ("Info", string, ansiColor (reset = True, bright = True, foreground = "white"), color)

def notice (string:str, color:bool = True):
	message ("Notice", string, ansiColor (reset = True, bright = True, foreground = "green"), color)

def warning (string:str, color:bool = True):
	message ("Warning", string, ansiColor (reset = True, bright = True, foreground = "yellow"), color)

def error (string:str, color:bool = True):
	message ("Error", string, ansiColor (reset = True, bright = True, foreground = "red"), color)

def fatal (string:str, color:bool = True):
	message ("Fatal", string, ansiColor (reset = True, bright = True, blink = True, foreground = "red"), color)
	os._exit (1)

def separator (character:str = "-", width:int = 80, color:bool = True, pad:bool = True):
	if pad == True:
		print ("")

	if color == True:
		print ("%s%s%s" % (ansiColor (reset = True, bright = True, foreground = "black"), character * width, ansiColor (reset = True)))
	else:
		print (character * width)

	if pad == True:
		print ("")

# ==============================================================================

SETTINGS_NEW = None

# ==============================================================================

def load_yaml (path:str) -> (dict, list):
	from yaml import load
	try:
		from yaml import CLoader as Loader, CDumper as Dumper
	except ImportError:
		from yaml import Loader, Dumper

	with open (path, "r") as file:
		return load (file, Loader = Loader)

# ==============================================================================

def request (
	method:str,
	url:str,
	params:dict = {},
	headers:dict = {},
	content:any = None,
	form:dict = None,
	json:object = None,
	http2:bool = None,
	timeout:float = 5.0
):
	import httpx as HTTPx
	import json as JSON

	if (
		(content is not None and form is not None) or
		(content is not None and json is not None) or
		(form is not None and json is not None)
	):
		raise ValueError ("Only one of content, form, and json may be specified")

	# --------------------------------------------------------------------------

	_headers = {}

	for key, value in headers.items ():
		_headers [key.lower ()] = value

	# --------------------------------------------------------------------------

	if json is not None:
		_content = JSON.dumps (json)

	if content is not None:
		_content = content
		_headers ["content-length"] = str (len (content))

	# --------------------------------------------------------------------------

	transport = HTTPx.HTTPTransport ()

	with HTTPx.Client (transport = transport, http2 = http2, headers = _headers, timeout = timeout) as client:
		request = HTTPx.Request (method.upper (), url, headers = headers, params = params, content = _content, data = form)
		response = client.send (request)

	# --------------------------------------------------------------------------

	return response

def get (url:str, params:dict = {}, headers:dict = {}, content:any = None, form:dict = None, json:object = None, http2:bool = None, timeout:float = None):
	return request ("GET", url, params, headers, content, form, json, http2, timeout)

def post (url:str, params:dict = {}, headers:dict = {}, content:any = None, form:dict = None, json:object = None, http2:bool = None, timeout:float = None):
	return request ("POST", url, params, headers, content, form, json, http2, timeout)

# ==============================================================================

def seconds_to_human (seconds:int) -> str:
	_seconds = seconds

	parts = []

	if _seconds >= 86400:
		parts.append ("%i day%s" % (
			int (_seconds / 86400),
			"s" if _seconds / 86400 > 1 else ""
		))
		_seconds %= 86400

	if _seconds >= 3600:
		parts.append ("%i hour%s" % (
			int (_seconds / 3600),
			"s" if _seconds / 3600 > 1 else ""
		))
		_seconds %= 3600

	if _seconds >= 60:
		parts.append ("%i minute%s" % (
			int (_seconds / 60),
			"s" if _seconds / 60 > 1 else ""
		))
		_seconds %= 60

	if _seconds > 0:
		parts.append ("%i second%s" % (
			_seconds,
			"s" if _seconds > 1 else ""
		))

	if len (parts) > 2:
		return ", ".join (parts [0:-1]) + ", and " + parts [-1]

	elif len (parts) == 2:
		return " and ".join (parts)

	elif len (parts) == 1:
		return parts [0]

	else:
		return "now!"

def offset_start (dow:int, hour:int, offset:int = 0) -> str:
	_hour = hour + offset
	if _hour < 0:
		_dow = dow - 1
		_hour += 24

	elif _hour > 23:
		_dow = dow + 1
		_hour -= 24

	else:
		_dow = dow

	if _dow < 0:
		_dow += 7

	elif _dow > 6:
		_dow -= 7

	return _dow, _hour

def get_next_start (day_of_week:int, hour:int):
	now = datetime.datetime.now (tz = datetime.timezone.utc) - datetime.timedelta (minutes = int (1))
	iterator = croniter (
		"0 %i * * %i" % (
			hour,
			day_of_week
		),
		now
	)
	return iterator.get_next (datetime.datetime)

def dow_to_name (dow:int) -> str:
	days = [
		"Sunday",
		"Monday",
		"Tuesday",
		"Wednesday",
		"Thursday",
		"Friday",
		"Saturday"
	]

	return days [dow]

def capitalize (text:str) -> str:
	import re

	return re.sub (r"(?i)\b([a-z])", lambda match: match [1].upper (), text)

def color_to_integer (red:(str, int), green:int = None, blue:int = None) -> int:
	import re

	named_colors = {
		"aqua": (0, 255, 255),
		"black": (0, 0, 0),
		"blue": (0, 0, 255),
		"fuchsia": (255, 0, 255),
		"gray": (128, 128, 128),
		"green": (0, 128, 0),
		"lime": (0, 255, 0),
		"maroon": (128, 0, 0),
		"navy": (0, 0, 128),
		"olive": (128, 128, 0),
		"purple": (128, 0, 128),
		"red": (255, 0, 0),
		"silver": (192, 192, 192),
		"teal": (0, 128, 128),
		"white": (255, 255, 255),
		"yellow": (255, 255, 0),
		"aliceblue": (240, 248, 255),
		"antiquewhite": (250, 235, 215),
		"aqua": (0, 255, 255),
		"aquamarine": (127, 255, 212),
		"azure": (1240, 255, 255),
		"beige": (245, 245, 220),
		"bisque": (255, 228, 196),
		"black": (0, 0, 0),
		"blanchedalmond": (255, 235, 205),
		"blue": (0, 0, 255),
		"blueviolet": (138, 43, 226),
		"brown": (165, 42, 42),
		"burlywood": (222, 184, 135),
		"cadetblue": (95, 158, 160),
		"chartreuse": (95, 158, 160),
		"chocolate": (210, 105, 30),
		"coral": (255, 127, 80),
		"cornflowerblue": (100, 149, 237),
		"cornsilk": (255, 248, 220),
		"crimson": (220, 20, 60),
		"cyan": (0, 255, 255),
		"darkblue": (0, 0, 139),
		"darkcyan": (0, 139, 139),
		"darkgoldenrod": (184, 134, 11),
		"darkgray": (169, 169, 169),
		"darkgreen": (0, 100, 0),
		"darkkhaki": (189, 183, 107),
		"darkmagenta": (139, 0, 139),
		"darkolivegreen": (85, 107, 47),
		"darkorange": (255, 140, 0),
		"darkorchid": (153, 50, 204),
		"darkred": (139, 0, 0),
		"darksalmon": (233, 150, 122),
		"darkseagreen": (143, 188, 143),
		"darkslateblue": (72, 61, 139),
		"darkslategray": (47, 79, 79),
		"darkturquoise": (0, 206, 209),
		"darkviolet": (148, 0, 211),
		"deeppink": (255, 20, 147),
		"deepskyblue": (0, 191, 255),
		"dimgray": (0, 191, 255),
		"dodgerblue": (30, 144, 255),
		"firebrick": (178, 34, 34),
		"floralwhite": (255, 250, 240),
		"forestgreen": (34, 139, 34),
		"fuchsia": (255, 0, 255),
		"gainsboro": (220, 220, 220),
		"ghostwhite": (248, 248, 255),
		"gold": (255, 215, 0),
		"goldenrod": (218, 165, 32),
		"gray": (127, 127, 127),
		"green": (0, 128, 0),
		"greenyellow": (173, 255, 47),
		"honeydew": (240, 255, 240),
		"hotpink": (255, 105, 180),
		"indianred": (205, 92, 92),
		"indigo": (75, 0, 130),
		"ivory": (255, 255, 240),
		"khaki": (240, 230, 140),
		"lavender": (230, 230, 250),
		"lavenderblush": (255, 240, 245),
		"lawngreen": (124, 252, 0),
		"lemonchiffon": (255, 250, 205),
		"lightblue": (173, 216, 230),
		"lightcoral": (240, 128, 128),
		"lightcyan": (224, 255, 255),
		"lightgoldenrodyellow": (250, 250, 210),
		"lightgreen": (144, 238, 144),
		"lightgrey": (211, 211, 211),
		"lightpink": (255, 182, 193),
		"lightsalmon": (255, 160, 122),
		"lightseagreen": (32, 178, 170),
		"lightskyblue": (135, 206, 250),
		"lightslategray": (119, 136, 153),
		"lightsteelblue": (176, 196, 222),
		"lightyellow": (255, 255, 224),
		"lime": (0, 255, 0),
		"limegreen": (50, 205, 50),
		"linen": (250, 240, 230),
		"magenta": (255, 0, 255),
		"maroon": (128, 0, 0),
		"mediumaquamarine": (102, 205, 170),
		"mediumblue": (0, 0, 205),
		"mediumorchid": (186, 85, 211),
		"mediumpurple": (147, 112, 219),
		"mediumseagreen": (60, 179, 113),
		"mediumslateblue": (123, 104, 238),
		"mediumspringgreen": (0, 250, 154),
		"mediumturquoise": (72, 209, 204),
		"mediumvioletred": (199, 21, 133),
		"midnightblue": (25, 25, 112),
		"mintcream": (245, 255, 250),
		"mistyrose": (255, 228, 225),
		"moccasin": (255, 228, 181),
		"navajowhite": (255, 222, 173),
		"navy": (0, 0, 128),
		"navyblue": (159, 175, 223),
		"oldlace": (253, 245, 230),
		"olive": (128, 128, 0),
		"olivedrab": (107, 142, 35),
		"orange": (255, 165, 0),
		"orangered": (255, 69, 0),
		"orchid": (218, 112, 214),
		"palegoldenrod": (238, 232, 170),
		"palegreen": (152, 251, 152),
		"paleturquoise": (175, 238, 238),
		"palevioletred": (219, 112, 147),
		"papayawhip": (255, 239, 213),
		"peachpuff": (255, 218, 185),
		"peru": (205, 133, 63),
		"pink": (255, 192, 203),
		"plum": (221, 160, 221),
		"powderblue": (176, 224, 230),
		"purple": (128, 0, 128),
		"red": (255, 0, 0),
		"rosybrown": (188, 143, 143),
		"royalblue": (65, 105, 225),
		"saddlebrown": (139, 69, 19),
		"salmon": (250, 128, 114),
		"sandybrown": (244, 164, 96),
		"seagreen": (46, 139, 87),
		"seashell": (255, 245, 238),
		"sienna": (160, 82, 45),
		"silver": (192, 192, 192),
		"skyblue": (135, 206, 235),
		"slateblue": (106, 90, 205),
		"slategray": (112, 128, 144),
		"snow": (255, 250, 250),
		"springgreen": (0, 255, 127),
		"steelblue": (70, 130, 180),
		"tan": (210, 180, 140),
		"teal": (0, 128, 128),
		"thistle": (216, 191, 216),
		"tomato": (255, 99, 71),
		"turquoise": (64, 224, 208),
		"violet": (238, 130, 238),
		"wheat": (245, 222, 179),
		"white": (255, 255, 255),
		"whitesmoke": (245, 245, 245),
		"yellow": (255, 255, 0),
		"yellowgreen": (139, 205, 50)
	}

	if isinstance (red, str):
		if red.lower () in named_colors:
			_red = named_colors [red.lower ()][0]
			_green = named_colors [red.lower ()][1]
			_blue = named_colors [red.lower ()][2]

		elif (parts := re.search (r"(?i)^(?:#|0x)?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$", red)) is not None:
			_red = int (parts [1], 16)
			_green = int (parts [2], 16)
			_blue = int (parts [3], 16)

		else:
			raise ValueError ("Unrecognized string form of color")

	elif red is not None and green is not None and blue is not None:
		_red = red
		_green = green
		_blue = blue

	else:
		raise ValueError ("Unrecognized arrangement of arguments")

	return (_red * 2 ** 16) + (_green * 2 ** 8) + _blue

def build_message (territory:dict, schedules:dict, durations:dict, region:str = "us") -> dict:
	start = get_next_start (
		schedules ["base"][territory ["name"]]["day"],
		schedules ["base"][territory ["name"]]["hour"]
	)

	mining_nodes = [
		"**%s**: %s%s" % (
			capitalize (system),
			capitalize (territory ["resources"][system]["type"]),
			" (%s)" % (
				u"\u2605" * territory ["resources"][system]["grade"]
			) if "grade" in territory ["resources"][system] else ""
		) for system in territory ["resources"].keys ()
	]
	if len (mining_nodes) == 0:
		mining_nodes = ["_none_"]

	particle_generators = []
	if "generators" in territory:
		for generator in ["standard", "advanced"]:
			if generator in (territory ["generators"] if isinstance (territory ["generators"], dict) else {}):
				particle_generators.append (
					"%s (%s)" % (
						capitalize (territory ["generators"][generator]),
						generator
					)
				)
	if len (particle_generators) == 0:
		particle_generators = ["_none_"]

	enhancers = []
	if "enhancers" in territory:
		for enhancer in ["standard", "advanced"]:
			if enhancer in (territory ["enhancers"] if isinstance (territory ["enhancers"], dict) else {}):
				enhancers.append (
					"%s (%s)" % (
						capitalize (territory ["enhancers"][enhancer]),
						enhancer
					)
				)
	if len (enhancers) == 0:
		enhancers = ["_none_"]

	improved_isogen = []
	if "improved-isogen" in territory:
		for improved in (territory ["improved-isogen"] if isinstance (territory ["improved-isogen"], list) else []):
			improved_isogen.append (
				u"\u2605" * improved
			)
	if len (improved_isogen) == 0:
		improved_isogen = ["_none_"]

	forges = [
		capitalize (forge) for forge in ["jelly", "sarcophagus"] if territory ["forges"][forge] == True
	]
	if len (forges) == 0:
		forges = ["_none_"]

	return {
		#"avatar_url": "https://cdn.stfc.io/territoria/avatar.png",
		"flags": 0,
		"allowed_mentions": {
			"parse": []
		},
		"content": "",
		"tts": False,
		"embeds": [
			{
				"provider": {
					"name": "Territoria",
					"url": "https://www.stfc.io/tools/territoria/"
				},
				"color": color_to_integer ("#808080"),
				"title": "%s (%s)" % (territory ["name"], u"\u25c6" * territory ["stars"]),
				"description": "",
				"fields": [
					{
						"name": "Takeover Start",
						"value": "<t:%i:t>" % (
							start.timestamp ()
						),
						"inline": True
					},
					{
						"name": "Duration",
						"value": "%im" % (durations [str (territory ["stars"])],),
						"inline": True
					},
					{
						"name": "Mining Nodes",
						"value": "\n".join (mining_nodes),
						"inline": True
					},
					{
						"name": "Particle Generators",
						"value": "\n".join (particle_generators),
						"inline": True
					},
					{
						"name": "Enhancers",
						"value": "\n".join (enhancers),
						"inline": True
					},
					{
						"name": "Improved Isogen Refinery",
						"value": "\n".join (improved_isogen),
						"inline": True
					},
					{
						"name": "Forges",
						"value": "\n".join (forges),
						"inline": True
					}
				],
				#"image": {
				#	"url": "https://cdn.stfc.io/territoria/maps/%s.png" % (territory ["name"].lower ())
				#}
			}
		]
	}

# ==============================================================================

def signalHandler (signal_number:int, frame):
	global SETTINGS_NEW

	if signal_number in (signal.SIGHUP):
		info ("Reloading settings")
		SETTINGS_NEW = load_yaml ("settings.yaml")

# ==============================================================================

def main ():
	global SETTINGS_NEW

	info ("Setting signal handlers")
	signal.signal (signal.SIGHUP, signalHandler)

	info ("Loading territory duration information")
	durations = load_yaml ("stfc-resources/data/territory/durations.yaml")
	info ("Loading territory takeover schedule")
	schedules = load_yaml ("stfc-resources/data/territory/schedules.yaml")
	info ("Loading territory information")
	territories = load_yaml ("stfc-resources/data/territory/information.yaml")

	info ("Loading settings")
	settings = load_yaml ("settings.yaml")

	# --------------------------------------------------------------------------

	# Prebuild messages
	info ("Prebuilding message structures")
	messages = {}
	for territory_name, territory in territories.items ():
		territory ["name"] = territory_name
		messages [territory ["name"]] = build_message (territory, schedules, durations)
	debug ("%i messages built" % (len (messages),))

	# --------------------------------------------------------------------------

	last_minute = int ((time.time () - 60) / 60)
	while True:
		# Switch to new settings if available
		if SETTINGS_NEW is not None:
			settings = SETTINGS_NEW
			SETTINGS_NEW = None

		# Only check once a minute
		current_minute = int (time.time () / 60)
		if last_minute == current_minute:
			continue
		else:
			last_minute = current_minute

		# Store the current time
		now = datetime.datetime.now (tz = datetime.timezone.utc)
		#now = datetime.datetime (year = 2022, month = 10, day = 31, hour = 22, minute = 0, second = 0, tzinfo = datetime.timezone.utc)

		# Go through each instance (id really isn't important, but meh)
		for instance_id, instance in settings ["instances"].items ():
			if "webhook" not in instance:
				continue

			# Go through each held system for the instance
			for system in instance ["held"]:
				# Go through each alert point
				for alert in instance ["alerts"]["countdown"]:
					# Check to see if it's the time for an alert
					if croniter.match (
						"0 %i * * %i" % (
							schedules ["base"][system]["hour"],
							schedules ["base"][system]["day"]
						),
						now + datetime.timedelta (minutes = int (alert))
					) == True:
						debug ("Prepping message for: %s -> %s @ %i" % (instance_id, system, alert))
						# Create a copy of the base message for the system
						message = messages [system].copy ()

						if instance ["tag"] == True:
							message ["content"] = "@everyone - "
							message ["allowed_mentions"]["parse"] = ["everyone"]

						message ["content"] += "**Starting %s%s**\n " % (
							"" if alert == 0 else "in ",
							seconds_to_human (alert * 60)
						)
						if alert >= 60:
							message ["embeds"][0]["color"] = color_to_integer (85, 255, 0)
						elif alert >= 30:
							message ["embeds"][0]["color"] = color_to_integer (255, 255, 0)
						elif alert >= 10:
							message ["embeds"][0]["color"] = color_to_integer (255, 85, 0)
						else:
							message ["embeds"][0]["color"] = color_to_integer (255, 0, 85)

						notice ("Sending message for: %s -> %s @ %i" % (instance_id, system, alert))
						post (
							url = instance ["webhook"],
							headers = {
								"Content-Type": "application/json"
							},
							json = message
						)

			for relationship in ["expansion", "ally"]:
				for related_id in instance [relationship]:
					for system in settings ["instances"][related_id]["held"]:
						# Go through each alert point
						for alert in instance ["alerts"]["countdown"]:
							# Check to see if it's the time for an alert
							if croniter.match (
								"0 %i * * %i" % (
									schedules ["base"][system]["hour"],
									schedules ["base"][system]["day"]
								),
								now + datetime.timedelta (minutes = int (alert))
							) == True:
								# Create a copy of the base message for the system
								message = messages [system].copy ()

								if instance ["tag"] == True:
									message ["content"] = "@everyone\n"
									message ["allowed_mentions"]["parse"] = ["everyone"]

								message ["content"] += "**Alliance:** %s\n**Relationship:** %s\n\n**Starting %s%s**\n " % (
									settings ["instances"][related_id]["name"],
									capitalize (relationship),
									"now!" if alert == 0 else "in ",
									seconds_to_human (alert * 60)
								)
								if alert >= 60:
									message ["embeds"][0]["color"] = color_to_integer (85, 255, 0)
								elif alert >= 30:
									message ["embeds"][0]["color"] = color_to_integer (255, 255, 0)
								elif alert >= 10:
									message ["embeds"][0]["color"] = color_to_integer (255, 85, 0)
								else:
									message ["embeds"][0]["color"] = color_to_integer (255, 0, 85)

								post (
									url = instance ["webhook"],
									headers = {
										"Content-Type": "application/json"
									},
									json = message
								)

		time.sleep (1)

if __name__ == "__main__":
	main ()

