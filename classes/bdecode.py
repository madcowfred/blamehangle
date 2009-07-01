def decode_int(x, f):
	f += 1
	newf = x.index('e', f)
	n = int(x[f:newf])
	if x[f] == '-':
		if x[f + 1] == '0':
			raise ValueError
	elif x[f] == '0' and newf != f+1:
		raise ValueError
	return (n, newf+1)

def decode_string(x, f):
	colon = x.index(':', f)
	n = int(x[f:colon])
	if x[f] == '0' and colon != f+1:
		raise ValueError
	colon += 1
	return (x[colon:colon+n], colon+n)

def decode_list(x, f):
	r, f = [], f+1
	while x[f] != 'e':
		v, f = decode_func[x[f]](x, f)
		r.append(v)
	return (r, f + 1)

def decode_dict(x, f):
	r, f = {}, f+1
	while x[f] != 'e':
		k, f = decode_string(x, f)
		r[k], f = decode_func[x[f]](x, f)
	return (r, f + 1)

decode_func = {}
decode_func['l'] = decode_list
decode_func['d'] = decode_dict
decode_func['i'] = decode_int
decode_func['0'] = decode_string
decode_func['1'] = decode_string
decode_func['2'] = decode_string
decode_func['3'] = decode_string
decode_func['4'] = decode_string
decode_func['5'] = decode_string
decode_func['6'] = decode_string
decode_func['7'] = decode_string
decode_func['8'] = decode_string
decode_func['9'] = decode_string

def bdecode(x):
	try:
		r, l = decode_func[x[0]](x, 0)
	except (IndexError, KeyError, ValueError):
		raise ValueError, 'not a valid bencoded string'
	if l != len(x):
		raise ValueError, 'invalid bencoded value (data after valid prefix)'
	return r

# ---------------------------------------------------------------------------
