#!/usr/bin/env python

'Script to generate a useful HTML page from plugin information.'

import os
import re
import sys

sys.path.append('.')

# ---------------------------------------------------------------------------

def main():
	html = open('docs/Plugins.html', 'w')
	
	# Spit out the header
	html.write(\
"""<html>
<head>
<title>blamehangle plugin docs</title>
<style type="text/css">
<!--
body {
	background: #123456;
	color: #FFFFFF;
	font-family: Arial, Helvetica, sans-serif;
}
h1 {
	text-align: center;
}
table {
	margin-bottom: 15px;
}
tr.name {
	background: #419481;
	text-align: center;
	font-size: 120%;
}
tr.desc {
	background: #449094;
}

-->
</style>
</head>

<body>
<h1>Plugins!</h1>
""")
	
	# Try to import our plugins
	plugins = [p[:-3] for p in os.listdir('plugins') if p.endswith('.py')]
	plugins.sort()
	
	for plugin in plugins:
		# Nothing to see here
		if plugin in ('__init__', 'NFOrce', 'SamplePlugin'):
			continue
		
		module = __import__('plugins.' + plugin, globals(), locals(), [plugin])
		
		if hasattr(module, '__doc__'):
			module_doc = module.__doc__
		else:
			module_doc = 'No description in file.'
		
		# Parse the plugin file looking for help. This is an ugly hack.
		pname = os.path.join('plugins', plugin) + '.py'
		lines = open(pname).read().splitlines()
		
		realcmds = []
		
		#bold_re = re.compile(r'\02(.+?)\02')
		
		for line in lines:
			line = line.strip()
			
			if line.startswith('help = ('):
				help_text = eval(line[7:-1])[2]
				
				# Strip stupid junk
				help_text = help_text.replace('\02', '')
				help_text = help_text.replace('<', '&lt;')
				help_text = help_text.replace('>', '&gt;')
				#help_text = bold_re.sub(r'<b>\1</b>', help_text)
				
				# Split it into useful bits
				command, help = help_text.split(' : ', 1)
				
				realcmds.append((command, help))
		
		
		# Spit out the info for this plugin
		html.write(\
"""<table align="center" cellspacing="1" cellpadding="2" width="750">
<tr class="name">
<td colspan="2">%s</td>
</tr>
<tr class="desc">
<td colspan="2">%s</td>
</tr>""" % (plugin, module_doc))
		
		
		realcmds.sort()
		for command, help in realcmds:
			html.write(\
"""<tr>
<td width="300">%s</td>
<td>%s</td>
</tr>
""" % (command, help))
		
		html.write("</table>\n")
	
	# Spit out the footer
	html.write(\
"""</body>
</html>
""")
	
	# And done
	html.close()

# ---------------------------------------------------------------------------

if __name__ == '__main__':
	main()
