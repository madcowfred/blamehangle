# ---------------------------------------------------------------------------
# $Id$
# ---------------------------------------------------------------------------
# This plugin does some stuff regarding flights and airlines.
# You can lookup an airline's code, or get details on a flight number.
# ---------------------------------------------------------------------------

from classes.Plugin import *
from classes.Constants import *
from cStringIO import *
import re, time, types

AIRLINE_LOOKUP = "AIRLINE_LOOKUP"
FLIGHT_SEARCH = "FLIGHT_SEARCH"

AIRLINE_RE = re.compile("^ *airline +(?P<airline>.+)$")

MAX_AIRLINE_MATCHES = 5

# what a bastard this was to get right. god damn i hate regexps.
f1 = "^ *flight +"
f2 = "(?P<code>[^ ]+)"
f3 = " +(?P<flight>[^ ]+)"
f4 = "(( *$)|( +%s *$))"
f5 = "(?P<year>20[0-9][0-9])-"
f6 = "(?P<month>(0[1-9])|(1[0-2]))-"
f7 = "(?P<day>(0[1-9])|([12][0-9])|(3[0-1]))"
f8 = f5+f6+f7
f9 = f4 % f8

FLIGHT_RE = re.compile(f1+f2+f3+f9)

class Airline(Plugin):
	"""
	stuff. it's 6:30am.

	and it was much later when i finished.
	comments come later
	"""

	def setup(self):
		pass
	
	def _message_PLUGIN_REGISTER(self, message):
		air_dir = PluginTextEvent(AIRLINE_LOOKUP, IRCT_PUBLIC_D, AIRLINE_RE)
		air_msg = PluginTextEvent(AIRLINE_LOOKUP, IRCT_MSG, AIRLINE_RE)
		fl_dir = PluginTextEvent(FLIGHT_SEARCH, IRCT_PUBLIC_D, FLIGHT_RE)
		fl_msg = PluginTextEvent(FLIGHT_SEARCH, IRCT_MSG, FLIGHT_RE)

		self.register(air_dir, air_msg, fl_dir, fl_msg)
	
	def _message_PLUGIN_TRIGGER(self, message):
		trigger = message.data
		
		if trigger.name == AIRLINE_LOOKUP:
			self.__airline_lookup(trigger)
		elif trigger.name == FLIGHT_SEARCH:
			self.__flight_search(trigger)
	

	def __airline_lookup(self, trigger):
		match = self.__airline_search(trigger)
		replytext = "Airline search for '%s'" % trigger.match.group('airline')
		if match:
			if type(match) == types.StringType:
				replytext += ": \02%s\02" % match
			elif type(match) == types.ListType:
				if len(match) > MAX_AIRLINE_MATCHES:
					replytext += " returned too many results. Please refine your query"
				else:
					replytext += " (\02%d\02 results): \02"
					replytext += "\02, \02".join(matches) + "\02"
			else:
				replytext += ": EEP something went wrong"
		else:
			replytext += " returned no results"

		self.sendReply(trigger, replytext)
	

	def __flight_search(self, trigger):
		code = trigger.match.group('code').upper()
		flight = trigger.match.group('flight')

		if not code in AIRLINES:
			replytext = "%s is not a valid airline carrier code" % code
			self.sendReply(trigger, replytext)
			return

		tolog = "code is %s" % code
		self.putlog(LOG_DEBUG, tolog)
		
		try:
			flight_num = int(flight)
		except ValueError:
			replytext = "\02'%s'\02 is not a valid number" % flight
			self.sendReply(trigger, replytext)
			return

		tolog = "flight is %s" % flight_num
		self.putlog(LOG_DEBUG, tolog)

		try:
			year = trigger.match.group('year')
			month = int(trigger.match.group('month'))
			day = trigger.match.group('day')
		except:
			currtime = time.localtime()
			year = currtime[0]
			month = currtime[1]
			day = currtime[2]
		
		tolog = "y:%s m:%s d:%s" % (year, month, day)
		self.putlog(LOG_DEBUG, tolog)
			
		# we have all the bits we need
		mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
			"Sep", "Oct", "Nov", "Dec" ]
		monthtxt = mon[month-1]
			
		url = "http://dps1.travelocity.com/dparflifo.ctl?CMonth=%s&CDayOfMonth=%s&CYear=%s&LANG=EN&last_pgd_page=dparrqst.pgd&dep_arpname=&arr_arp_name=&dep_dt_mn_1=%s&dep_dt_dy_1=%s&dep_tm1=12%%3A00pm&aln_name=%s&flt_num=%s&Search+Now.x=89&Search+Now.y=4" % (month, day, year, monthtxt, day, code, flight)
		self.sendMessage('HTTPMonster', REQ_URL, [url, trigger])
	
	def _message_REPLY_URL(self, message):
		page_text, trigger = message.data
		
		# this ugly parsing is ripped right from the pinky java.
		# .. much like the rest of this plugin, really
		s = StringIO(page_text)
		sub = re.sub
		tag = "<.+?>"
		nbsp = "&nbsp;"
		found = 0
		line = s.readline()
		while line:
			if line.lower() == "<td valign=top align=right nowrap><b>city:</b>&nbsp;</td>\n":
				line = s.readline()
				source = self.__rip(line)
				line = s.readline()
				line = s.readline()
				dest = self.__rip(line)
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				source_sched = self.__rip(line)
				line = s.readline()
				line = s.readline()
				dest_sched = self.__rip(line)
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				source_act = self.__rip(line)
				line = s.readline()
				line = s.readline()
				dest_act = self.__rip(line)
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				source_gate = self.__rip(line)
				line = s.readline()
				line = s.readline()
				dest_gate = self.__rip(line)
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				line = s.readline()
				dest_bags = self.__rip(line)

				found = 1
				# once we have found something, always reply in msg
				#trigger.event.IRCType = IRCT_MSG

				replytext = "\02Departure\02: %s - %s (%s) Gate: %s" % (source, source_sched, source_act, source_gate)
				replytext += " --> \02Arrival\02: %s - %s (%s) Gate: %s Baggage: %s" % (dest, dest_sched, dest_act, dest_gate, dest_bags)
				self.sendReply(trigger, replytext)

			line = s.readline()
		
		if not found:
			replytext = "Error finding flight"
			self.sendReply(trigger, replytext)
	
	def __rip(self, text):
		text = re.sub("<.+?>", "", text)
		text = re.sub("&nbsp;", " ", text)
		return text[:-1]
	
	def __airline_search(self, trigger):
		airtext = trigger.match.group('airline')
		if len(airtext) == 2:
			airtext = airtext.upper()
			# this is a code
			if airtext in AIRLINES:
				return AIRLINES[airtext]
		else:
			# this is a name
			airtext = airtext.lower()
			matches = []
			for code, name in AIRLINES.items():
				if name.lower().startswith(airtext):
					matches.append(code)
					print "found a match! %s" % code

			if len(matches) == 1:
				return matches[0]
			else:
				return matches









# lots of white space here so you don't have to have that evil line on the
# screen.













# it's ugly :(













AIRLINES = {'WX': 'Cityjet', 'QF': 'Qantas Airways Ltd', 'JX': 'Skybus Kal', 'WB': 'SAN', 'G7': 'Guinee Airlines SA', 'G6': 'Volga Airlines', 'G5': 'Island Air Ltd', 'G4': 'Guizhou Airlines', 'G3': 'Emerald Airways', 'JZ': 'Skyways Ab', 'G9': 'Grant Aviation', 'G8': 'Gujarat Airways Ltd', 'WO': 'World Airways', 'QI': 'Cimber Air', 'JU': 'Yugoslav Airlines', 'WM': 'Windward Island Airways', 'GW': 'Air Lines of Kuban', 'GV': 'Riga Airlines', 'GU': 'Aviateca', 'GT': 'GB Airways', 'GS': 'Grant Aviation', 'GR': 'Aurigny Air Services', 'GQ': 'Big Sky Airlines', 'GP': 'China General Aviation', 'GZ': 'Air Rarotonga', 'GY': 'Guyana Airways', 'GX': 'Pacific Airways Corp', 'GG': 'Tamair', 'GF': 'Gulf Air', 'GE': 'Transasia Airways', 'F3': 'Flying Enterprise', 'GC': 'Lina Congo', 'GB': 'Air Glaciers SA', 'GA': 'Garuda Indonesia', 'GO': 'Air Stord', 'GN': 'Air Gabon', 'GM': 'Air Slovakia BWJ', 'JS': 'Air Koryo', 'GK': 'Go One Airways', 'GJ': 'Eurofly Spa', 'GI': 'Air Guinee', 'GH': 'Ghana Airways', 'WW': 'Whyalla Airlines Pty Ltd', 'JM': 'Air Jamaica', 'H5': 'Magadan Airlines', 'F8': 'Western Ailines', 'WT': 'Nigeria Airways', 'VO': 'Tyrolean Airways', 'SR': 'Swissair', 'JH': 'Nordeste Linhas Aereas', 'AR': 'Aerolineas Argentinas', 'WR': 'Royal Tongan Airlines', '3Z': 'Necon Air', '3Y': 'Britrail', '3X': 'Japan Air Commuter', 'JJ': 'TAM Meridional', '3S': 'Shuswap Air', '3R': 'Air Moldova International', '3Q': 'China Yunnan Airlines', '3P': 'Georgian Airlines', '3W': 'Nanjing Airlines', '3U': 'Sichuan Airlines', '3T': 'Turan Air Airline Company', 'M5': 'Kenmore Air', '3J': 'Air Alliance', 'M7': 'Macedonian Airlines', 'M6': 'Chalair', 'VP': 'Vaspbrazilian Airlines', '3N': 'Air Urga', '3M': 'Gulfstream International', 'M2': 'Mahfooz Aviation G Ltd', '3C': 'Corporate Express Airline', '3B': 'Avior', '3A': 'Mafira Air', 'M9': 'Modiluft Ltd', 'M8': 'Moscow Airways', '3E': 'Northwestern Air Lease', '3D': 'Palair Macedonian Air', 'JA': 'Air Bosna', 'T8': 'Transportes Aereos Neuqu', 'Z8': 'Dhl de Guatemala SA', 'Z9': 'Aero Zambia', 'Z4': 'Tayfunair Inc', 'Z5': 'Newwest Airlines Inc', 'Z6': 'Dnieproavia State', 'Z7': 'Zimbabwe Express Air', 'Z3': 'Promech', 'ZL': 'Hazelton Airlines', 'ZM': 'Scibe Airlift', 'ZN': 'Eagle Airlines', 'ZH': 'Air Truck', 'ZI': 'Aigle Azur', 'ZJ': 'Teddy Air', 'ZK': 'Great Lakes Aviation Ltd', 'ZE': 'Cosmos Air', 'ZF': 'Airborne of Sweden AB', 'ZG': 'Sabair Airlines', 'ZA': 'ZAS Airline of Egypt', 'ZB': 'Monarch Airlines', 'ZC': 'Royal Swazi National Air', 'ZX': 'Air B C', 'ZY': 'ADA Air', 'ZT': 'Satena', 'ZU': 'Freedom Air', 'ZV': 'Air Midwest', 'ZW': 'Air Wisconsin Airlines', 'ZP': 'Air St Thomas', 'ZQ': 'Ansett New Zealand', 'ZR': 'MUK Air', 'ZS': 'Azzurra Air Spa', 'ME': 'Middle East Airlines', 'MD': 'Air Madagascar', 'MG': 'Djibouti Airlines', 'MF': 'Xiamen Airlines', 'MA': 'Malev Hungarian Airlines', 'MC': 'Air Mobility Command', 'MB': 'Western Airlines', 'MM': 'Soc Aero de Medellin', 'ML': 'Aero Costa Rica Acori', 'MO': 'Calm Air International', 'MN': 'Commercial Airways', 'MI': 'Silkair', 'MH': 'Malaysian Airline', 'MK': 'Air Mauritius', 'MJ': 'Lapa', 'MU': 'China Eastern Airlines', 'MT': 'Flying Colours Airlines', 'MW': 'Maya Airways', 'MV': 'Great American Airways', 'MQ': 'Simmons Airlines', 'MP': 'Martinair Holland', 'MS': 'Egyptair', 'MR': 'Air Mauritanie', 'MY': 'Euroscot Airways Ltd', 'MX': 'Mexicana', 'MZ': 'Merpati', 'FP': 'Aeroleasing SA', 'FQ': 'Air Aruba', 'FR': 'Ryanair', 'S8': 'Estonian Aviation', 'FT': 'Vancouver Island Air Ltd', 'FU': 'Air Littoral', 'FV': 'F Airlines B V', 'S3': 'Astoria', 'FY': 'Hahnair Friedrichshafen', 'FZ': 'Air Facilities', 'S7': 'Siberia Airlines', 'S6': 'Air St Martin', 'S5': 'Virgin Islands Airways', 'S4': 'Spair Air Transport', 'FA': 'Finnaviation', 'FB': 'Executive Air', 'FC': 'Thuringia Airlines', 'FD': 'Cityflyer Express', 'FE': 'Eagle Canyon Airlines', 'FF': 'Tower Air Inc', 'FG': 'Ariana Afghan Airlines', 'FH': 'Futura International', 'FI': 'Icelandair', 'FJ': 'Air Pacific Ltd', 'FK': 'Flamenco Airways', 'FL': 'Airtran Airways', 'FM': 'Shanghai Airlines', 'FN': 'Regional Air Lines', 'FO': 'Expedition Airways', '9K': 'Cape Air', '9J': 'Pacific Island Aviation', '9M': 'Central Mountain Air', '9L': 'Colgan Air', '9N': 'Trans State Airlines', '9A': 'Air Atlantic', '9C': 'Gill Aviation Ltd', '9B': 'Intourtrans', '9E': 'Express Airlines', 'UU': 'Air Austral', '9G': 'Caribbean Air', '9F': 'Majestic Airways', '9Y': 'Air Kazakstan', '9X': 'Tasawi Air Services Ltd', '9P': 'Pelangi Air', '9R': 'Air Kilroe Limited', '9U': 'Air Moldova', '9T': 'Athabaska Airways', '9W': 'Jet Airways Ltd', '9V': 'VIP Air', 'WI': 'U Land Airlines', 'M4': 'Interimpex Avioimpex', 'UT': 'Air Charter Asia', 'JQ': 'Trans Jamaican Airlines', 'SZ': 'China Southwest Airlines', 'F2': 'Southern Independent Air', 'SX': 'Aeroejecutivo SA de CV', 'F4': 'Eureca SRL', 'F5': 'Archana Airways Ltd', 'F6': 'China National Aviation', 'F7': 'Iron Dragon Fly Air Co', 'SS': 'Corse Air International', 'F9': 'Frontier Airlines', 'SQ': 'Singapore Airlines', 'SP': 'Sata Air Acores', 'SW': 'Air Namibia', 'SV': 'Saudi Arabian Airlines', 'SU': 'Aeroflot Russian', 'ST': 'Yanda Airlines', 'SK': 'Scandinavian Airlines', 'SJ': 'Southern Air Transport', 'SI': 'Sierra Pacific Airlines', 'SH': 'Air Toulouse', 'SO': 'Sunshine Air', 'SN': 'Sabena', 'SM': 'Sunworld Intl Airlines', 'SL': 'Rio Sul', 'SC': 'Shandong Airlines', 'SB': 'Air Cal\xe9donie International', 'SA': 'South African Airways', 'SG': 'Sempati Air', 'SF': 'Air Charter', 'SE': 'Wings of Alaska', 'SD': 'Sudan Airways Co Ltd', 'YI': 'Air Sunshine', 'YH': 'Air Nunavut', 'YK': 'Kibris Turk Hava Yollari', 'YJ': 'National Airlines', 'YM': 'Blue Sky Carrier', 'YL': 'Long Island Airlines Ltd', 'YO': 'Heli Air Monaco', 'YN': 'Air Creebec', 'YA': 'Nego Airline One', 'UQ': 'O Connor Mt Gambiers', 'YC': 'Flight West Airlines', 'YB': 'South African Express', 'YE': 'Emerald European Airways', 'YD': 'Gomelavia', 'H7': 'Taquan Air Service Inc', 'YX': 'Midwest Express Airlines', 'YZ': 'Trans Aer Guine Bissau', 'US': 'US Airways', '3H': 'Air Inuit Ltd', 'YQ': 'Helikopterservice', 'YP': 'Aero Lloyd Flugreisen', 'YS': 'Proteus', 'YR': 'Scenic Airlines', 'YU': 'Aerolineas Dominicanas', 'YT': 'Skywest Airlines', 'YW': 'Air Nostrum', 'YV': 'Mesa Airlines', 'LF': 'Jet Train Corp', 'LG': 'Luxair', 'LD': 'Lineas Aereas del Estado', 'LE': 'Helgoland Airlines', 'LB': 'Lloyd Aero Boliviano', 'LC': 'Loganair', 'LA': 'Lan Chile', 'LN': 'Libyan Airlines', 'LO': 'LOT Polish Airlines', 'LL': 'Lineas Aereas Allegro', 'LM': 'Antillean Airlines', 'LJ': 'Sierra National Airlines', 'LK': 'Fairlines', 'LH': 'Lufthansa', 'LI': 'Liat Caribbean Airline', 'LV': 'Albanian Airlines Mak', 'LW': 'Air Nevada', 'LT': 'LTU', 'LU': 'Air Atlantic Dominicana', 'LR': 'Lacsa Airlines', 'LS': 'Iliamna Air Taxi Inc', 'LP': 'Euro City Line', 'LQ': 'Airpac Airlines', 'LZ': 'Balkan', 'LX': 'Crossair', 'LY': 'El Al Israel Airlines', 'L6': 'Air Maldives Ltd', 'L7': 'Lviv Airlines', 'L4': 'Atlant Sv', 'L5': 'Lufttransport', 'L2': 'Lynden Air Cargo', 'L3': 'Kaiken Lineas Aereas', 'L8': 'European Airways Ltd', 'L9': 'Air Mali SA', 'OR': 'Crimea Air', 'Y9': 'Trans Air Congo', 'Y8': 'Passadero Trans Aereos', 'GD': 'Trans Aereos Ejecutivos', 'Y3': 'Asia Service Airlines', 'Y2': 'Alliance', 'Y5': 'Arax Airways', 'Y4': 'Eagle Aviation Ltd', 'Y7': 'Iran Asseman Airlines', 'Y6': 'Europe Elite', 'RT': 'Lincoln Airlines', 'RU': 'TCI Skyking Ltd', 'RV': 'Reeve Aleutian Airways', 'RW': 'Ras Fluggesellschaft MBH', 'RP': 'Precision Airlines', 'RQ': 'Air Engiadiana', 'RR': 'Royal Air Force', 'RS': 'Intercont de Aviaci\xf3n', 'RX': 'Redwing Airways Inc', 'RY': 'Air Rwanda', 'RZ': 'Sansa', 'RD': 'Alitalia Team', 'RE': 'Aeronautica de Cancun', 'RF': 'Florida West Airlines', 'RG': 'Varig', 'RA': 'Royal Nepal Airlines', 'RB': 'Syrianair', 'RC': 'Atlantic Airways', 'RL': 'Region Air Carribean Ltd', 'RM': 'Wings West Airlines', 'RN': 'Euralair International', 'RO': 'Tarom', 'RI': 'P T Mandala Airlines', 'RJ': 'Royal Jordanian', 'RK': 'Air Afrique', '2T': 'Canada Three Thousand', 'R5': 'Malta Air Charter', 'R6': 'Cypress Airlines', 'R7': 'Aeroservicios Carabobo', '2P': 'Air Philippines Corp', '2Q': 'Millenium Air Corp', 'R2': 'State Orenburg Avia', 'R3': 'Armenian Airlines', 'R8': 'Reguljair', '2Y': 'Helenair Corporation Ltd', '2Z': 'Changan Airlines', '2D': 'Denim Air', '2E': 'Ireland Airways', '2F': 'Frontier Flying Service', '2G': 'Debonair Airways', '2A': 'Deutsche Bahn AG', '2B': 'Aerocondor Trans Aereos', '2L': 'Karlog Air', '2M': 'Moldavian Airlines', '2N': 'Haiti Aviation', '2H': 'European Airlines', '2J': 'Air Burkina', '2K': 'Kitty Hawk Airlines Inc', 'VA': 'Viasa Venezolana', 'B9': 'Caribbean Airlines Inc', 'VC': 'Servicios Avensa', 'VH': 'Aeropostal Alas', 'E9': 'Ajt Air International', 'E8': 'Alpi Eagles Spa', 'VI': 'Vieques Air Link', 'E5': 'Samara Airlines', 'E4': 'Aero Asia International', 'E7': 'Downeast Express', 'E6': 'Air Company Elf Air', 'VJ': 'Royal Air Cambodge', 'E3': 'Domodedovo Airlines', 'E2': 'Everest Air Ltd', 'EM': 'Western Airlines', 'EL': 'Air Nippon Co Ltd', 'EO': 'Alliance Airlines', 'EN': 'Air Dolomiti Spa', 'EI': 'AER Lingus Limited', 'EH': 'Saeta', 'EK': 'Emirates', 'EJ': 'New England Airlines', 'ED': 'Ccair', 'EG': 'Japan Asia Airways', 'EF': 'Far Eastern Air Transport', 'EA': 'Eas Europe Airlines', 'EC': 'Heli Inter Riviera', 'VM': 'Regional Airlines', 'EY': 'Mayan World Airlines', 'EX': 'Aerolineas Santo Domingo', 'EZ': 'Sun Air Of Scandinavia', 'EU': 'Ecuatoriana De Aviaci\xf3n', 'ET': 'Ethiopian Airlines', 'EW': 'Eurowings', 'EV': 'Atlantic Southeast Airlines', 'EQ': 'Tame', 'EP': 'Pelita Air Service', 'ES': 'Helicopteros Del Cusco', 'ER': 'Air East', '8J': 'Jetall', '8K': 'Air Ostrava Ltd', '8H': 'Air South West', '8N': 'Flagship Airlines', '8O': 'West Coast Air', '8L': 'Grand International Airway', '8M': 'Mahalo Air Inc', '8B': 'Baker Aviation Inc.', '8C': 'Shanxi Airlines', '8A': 'Americana De Aviaci\xf3n', '8F': 'Hanair Haiti Ntl Air', 'VR': 'TACV Cabo Verde Airlines', '8D': 'Awood Air Ltd', '8E': 'Bering Air', '8Z': 'Alaska Island Air Inc', '8Y': 'Ecuato Guineana De Aviac', '8R': 'Rock Air', '8S': 'Salair Inc', '8P': 'Pacific Coastal Airlines', '8Q': 'Baker Aviation', '8V': 'Wright Air Services', '8T': 'Air Tindi Ltd', '8U': 'Dolphin Express Airlines', 'IN': 'Macedonian Airlines', 'SY': 'Sun Country Airlines', 'K3': 'Air Company Kraiaero', 'K2': 'Kyrghyzstan Airlines', 'K7': 'National Air Sakha Aviation', 'K6': 'Appolo Airlines S A', 'K5': 'Wings Of Alaska', 'K4': 'Kazakhstan Airlines', 'K9': 'Itapemirim Transportes', 'K8': 'Kaliningrad Airlines', 'IC': 'Indian Airlines Ltd', 'HR': 'Hahn Air', 'X8': 'Aerovias Dap SA', 'X2': 'China Xinhua Airlines', 'X3': 'Baikal Airlines', 'X6': 'Khors Aircompany Ltd', 'X7': 'Joint Stock Company', 'X4': 'Haiti Trans Air', 'X5': 'Cronus Airlines', 'XJ': 'Mesaba Airlines', 'XK': 'Corse M\xe9diterran\xe9e', 'XO': 'Xinjiang Airlines', 'XL': 'Country Connections Airline', 'XM': 'Alitalia Express', 'XC': 'K D Air Corporation', 'XG': 'Regional Lineas Aereas', 'XE': 'Cambodia Intl Airlines', 'XZ': 'Eastair', 'XX': 'SAL - Saxiona Airlines', 'XY': 'Ryan Air', 'M3': 'Aerolinhas Bresileiras', 'XP': 'Casino Express Airlines', 'XQ': 'Action Airlines', 'XV': 'Air Express', 'XT': 'Air Exel NL', 'XU': 'Link Airways', 'KC': 'Australian Commuter Air', 'KB': 'Druk Air', 'KA': 'Hong Kong Dragon Airline', 'KG': 'Linea Aerea IAACA', 'KF': 'Air Botnia', 'KE': 'Korean Air', 'KD': 'Kendell Airlines', 'KK': 'Tam Regional', 'KJ': 'British Mediterranean', 'KH': 'Kyrnair', 'KO': 'Alaska Central Express', 'KN': 'Coral International Air', 'KM': 'Air Malta', 'KL': 'KLM', 'KS': 'Penair', 'KR': 'Kar Air', 'KQ': 'Kenya Airways', 'KP': 'Kiwi International Air', 'KW': 'Carnival Airlines', 'KV': 'Transkei Airways', 'KU': 'Kuwait Airways', 'KT': 'Kampuchea Airlines', 'KZ': 'Linea Aerea Ejecutivo', 'KY': 'Waterwings Airways', 'KX': 'Cayman Airways Ltd', '5C': 'Conquest Airlines', 'DN': 'Trans Pacific Airlines', 'DO': 'Compan\xeda Dominicana', 'Q3': 'Sandaun Air Services', 'Q2': 'Minerva Airlines', 'Q5': 'Forty Mile Air', 'DK': 'Eastland Air', 'Q7': 'Sobelair', 'DI': 'Deutsche BA', 'Q9': 'Interbrasil Star S.A.', 'DG': 'Island Airlines Pty', 'DD': 'Shuttle Air Cargo', 'DE': 'Condor Flugdienst', 'DB': 'Brit Air', 'DC': 'Golden Air Flyg Ab', 'T5': 'Aviacompany Turkmenistan', 'DA': 'Air Georgia', 'AT': 'Royal Air Maroc', 'DZ': 'Transcaraibes Air Intl', 'DX': 'Danish Air Transport', 'DY': 'Air Djibouti', 'DV': 'Gorda Aero Service', 'DW': 'Rottnest Airlines', 'DT': 'Taag', 'DU': 'Hemus Air', 'DR': 'Air Link Pty', 'DS': 'Air Senegal', 'DP': 'Air Two Thousand Ltd', 'DQ': 'Coastal Air Transport', '7G': 'Bellair Inc', '7F': 'First Air', '7E': 'Nepal Airways', '7C': 'Columbia Pacific Airline', '7B': 'Krasnoyarsk Airlines', '7A': 'Haines Airways', '7N': 'Air Manitoba', '3K': 'Tatonduk Flying Service', '7L': 'Air Bristol Dba Ab Airline', '7K': 'Larrys Flying Service', '7J': 'State Air Company Tajikistan', '7I': 'Imperial Air', '3F': 'First American Railways', '7W': 'Air Sask Aviation', '7V': 'Alpha Air', '7U': 'Avianergo', '7T': 'Trans Cote', '7S': 'Arctic Transportation', '7R': 'Redwing Airways', '7Q': 'Shorouk Air', '7P': 'Apa International Air', '7Z': 'L.B.Limited', '7Y': 'West Isle Air', '7X': 'Aea International Pte', 'QH': 'Qwestair', 'T3': 'Tristar Airlines', '00': 'Default Test Airline', 'QQ': 'Reno Air Inc', 'QP': 'Air Kenya Aviation', 'QS': 'Tatra Air', 'QR': 'Qatar Airways WLL', 'QU': 'Uganda Airlines', 'QT': 'Sar Avions Taxis', 'QW': 'Turks and Caicos Airways', 'QV': 'Lao Aviation', 'QY': 'European Air Transport', 'QX': 'Horizon Air', 'QZ': 'Zambia Airways Corp.', 'QA': 'Aerocaribe', 'QC': 'Air Zaire', 'QB': 'Northern Airlines Sanya', 'QE': 'European Continental Air', 'QD': 'Grand Airways', 'D8': 'Diamond Sakha Airlines', 'D9': 'Joint Stock Aviation Co', 'D6': 'Inter Air', 'D7': 'Dinar Lineas Aereas SA', 'QK': 'Air Nova', 'D5': 'Nepc Airlines', 'QM': 'Air Malawi Limited', 'QL': 'Lesotho Airways', 'QO': 'Aeromexpress', 'QN': 'Ord Air Charter Pty Ltd', 'WG': 'Wasaya Airways Ltd', 'WF': 'Wideroe', 'WE': 'Rheintalflug Seewald', 'WD': 'Halisa Air', 'WC': 'Islena de Inversiones SA', 'JY': 'Jersey European', 'WA': 'Newair', 'JT': 'Jaro Intl Airlines', 'WN': 'Southwest Airlines Texas', 'JV': 'Bearskin Airlines', 'WL': 'Aeroperlas', 'JP': 'Adria Airways', 'WJ': 'Labrador Airways Ltd', 'JR': 'Aero California', 'WH': 'China Northwest Airlines', 'JL': 'JAL Japan Airlines', 'WV': 'Air South Airlines Inc', 'JN': 'Rich International Air', 'JO': 'Eurosky Airlines', 'WS': 'Air Caraibes', 'JI': 'Midway Airlines', 'WQ': 'Romavia', 'WP': 'Aloha Islandair', 'JD': 'Japan Air System Company', 'JE': 'Manx Airlines', 'JF': 'L A B Flying Service', 'JG': 'Air Greece Aerodromisis', 'WZ': 'Acvilla Air', 'JB': 'Helijet Airways', 'JC': 'Inter Air Direct', 'BC': 'Air Jet', 'BL': 'Pacific Airlines', '4Z': 'South African Airlink', 'BM': 'Air Sicilia', '5W': 'Executive Express Ltd.', '5V': 'Vistajet', 'BH': 'Transtate Airlines', 'BI': 'Royal Brunei', '4Y': 'Yute Air Alaska', 'BK': 'Paradise Island', 'BT': 'Air Baltic Corp', 'J8': 'Berjaya Air', 'J9': 'Jet Aspen', 'BU': 'Braathens Safe', 'J4': 'Buffalo Airways Ltd', 'J5': 'Aviaprima Airlines', 'J6': 'Larrys Flying Service', 'J7': 'Valujet Airlines', 'J2': 'Azerbaijan Hava Yollari', 'W7': 'Western Pacific Airlines', 'W5': 'Tajikistan International', 'W4': 'Aero Services Executive', 'W3': 'Swiftair SA', 'W9': 'Eastwind Capital Partner', 'W8': 'Carribean Winds Airlines', '5K': 'State Air Company Odessa', '5J': 'Cebu Pacific Air', '4W': 'Warbelows Air Ventures', '4V': 'Voyageur Airways', 'PR': 'Philippine Airlines', 'PS': 'Ukraine Intl Airlines', 'PP': 'Jet Aviation Business AG', 'PQ': 'Skippers Aviation Pty Lt', 'PV': 'Pauknair', 'PW': 'Pine State Airlines', 'PT': 'West Air Sweden', 'PU': 'Pluna', 'PZ': 'Tra.Aereos del Mercosur', '5A': 'Alpine Aviation', 'PX': 'Air Niugini', 'PY': 'Surinam Airways', 'PB': 'Air Burundi', 'PC': 'Air Fiji Ltd', 'PA': 'Pan Am World Airways', 'PF': 'Vayudoot', 'PG': 'Bangkok Airways', 'PD': 'Pemair', 'PE': 'Helisul Linhas Aereas', 'PJ': 'Air St Pierre', 'PK': 'Pakistan International', 'PH': 'Polynesian Ltd', 'PI': 'Sunflower Airlines', 'PN': 'Ste Nlle Air Martinique', 'PL': 'Aeroperu', 'PM': 'Tropic Air', 'P2': 'Tymen Air Carrier', 'P3': 'Air Provence', 'P6': 'Trans Air', 'P7': 'Joint Stock Co East Line', 'P4': 'Aero Lineas Sosa', 'P5': 'Aerorepublica', 'P8': 'Pantanal Linhas Aereas', '5N': 'Aerotour Dominicano Airline', 'DL': 'Delta Air Lines', 'DM': 'Maersk Air', 'DJ': 'Nordic European Airlines', 'Q4': 'Mustique Airways', 'DH': 'United Express', 'FS': 'Missionary Aviation', 'Q6': 'Aviation Mineralnye Vody', 'DF': 'Aviosarda', 'C9': 'Co A\xe9ronautique Europ\xe9en', 'C8': 'Chicago Express Airlines', 'Q8': 'Donetsk Aviation', 'C3': 'Angola Air Charter', 'C2': 'Air Caribbean Ltd', 'C7': 'Bonaire Airways', 'C6': 'Bright Air', 'C5': 'Cretan Airlines SA', 'C4': 'Airlines Of Carriacou', 'CK': 'Andesmar Lineas Aereas', 'CJ': 'China Northern Airlines', 'CI': 'China Airlines', 'CH': 'Bemidji Airlines', 'CO': 'Continental Airlines', 'CN': 'Island Nationair', 'CM': 'Copa Compan\xeda Panamena', 'CL': 'Lufthansa Citylin', 'CC': 'Macair Airlines', 'CB': 'Suckling Airways', 'CA': 'Air China International', 'CG': 'Milne Bay Air Pty', 'CF': 'Faucett', 'CE': 'Nationwide Air', 'CD': 'Alliance Air', 'CZ': 'China Southern Airlines', 'CY': 'Cyprus Airways', 'CX': 'Cathay Pacific', 'CS': 'Continental Micro', 'CQ': 'Air Alpha', 'CP': 'Canadian Airlines', 'CW': 'Air Marshall Islands Inc', 'CV': 'Air Chathams', 'CU': 'Cubana de Aviaci\xf3n', 'CT': 'Northwestern Air Lease', '6A': 'Aviacsa', '6B': 'Baxter Aviation', '6C': 'Cape Smythe Air Service', '6D': 'Alaska Island Air Inc', '6E': 'Malmo Aviation', '6F': 'Laker Airways Inc', '6G': 'Las Vegas Airlines', '6J': 'Southeast European Air', '6K': 'Korsar', '6L': 'Aklak Inc', '6M': 'Maverick Airways Corp', '6N': 'Trans Travel Airlines', '6P': 'Dac Air', '6Q': 'Slovak Airlines', '6R': 'Air Affaires Afrique', '6S': 'Proteus Helicopters', '6T': 'Air Mandalay Ltd', '6U': 'Air Ukraine', '6V': 'Air Vegas', '6W': 'Wilderness Airlines', 'HP': 'America West Airlines', '6Y': 'Nica', 'R4': 'Russia', '2U': 'Western Pacific Air', '2V': 'Amtrak', '2W': 'Pacific Midland Airlines', '2R': 'Via Rail Canada Inc.', '2S': 'Island Express', 'D4': 'Aries del Sur', 'V2': 'Valdresfly AS', 'V3': 'Vanair Limited', 'V4': 'Venus Airlines', 'V5': 'Vnukovo Airlines', 'V6': 'Orient Avia', 'V8': 'Contact Air', 'V9': 'Bashkir Airlines', 'IY': 'Yemenia', 'IX': 'Flandre Air', 'VB': 'Maersk Air Ltd', 'IZ': 'Arkia Israeli Airlines', 'VD': 'Air Libert\xe8', 'VE': 'Aerovias Venezolanas', 'VF': 'Tropical Airlines', 'VG': 'VLM Vlaamse', 'IQ': 'Augsburg Airways', 'IP': 'Airlines of Tasmania', 'IS': 'Island Airlines', 'VK': 'Air Tungaru', 'VL': 'North Vancouver Airlines', 'IT': 'Air Inter Europe', 'IW': 'AOM French Airlines', 'IV': 'Fujian Airlines', 'II': 'Business Air Ltd', 'VQ': 'Impulse Airlines Ltd', 'IK': 'Lynden Air Cargo', 'VS': 'Virgin Atlantic', 'VT': 'Air Tahiti', 'VU': 'Air Ivoire', 'VV': 'Aerosweet', 'VW': 'Aeromar Airlines', 'VX': 'Aces', 'VY': 'Formosa Airlines Corp.', 'VZ': 'Airtours Intl Airways', 'IB': 'IBERIA', 'IE': 'Solomon Airlines', 'ID': 'Air Normandie', 'IG': 'Meridiana Spa', 'IF': 'Great China Airlines', 'WY': 'Oman Air', 'IH': 'Falcon Aviation AB', '7M': 'Tyumen Airlines', 'S9': 'SK Air A.S', 'BD': 'British Midland Airways', 'BE': 'Centennial Airlines SA', 'BF': 'Markair', 'BG': 'Biman Bangladesh Airline', '5Y': 'Isles Of Scilly Skybus', 'BA': 'British Airways', 'BB': 'Seaborne Aviation Inc', '5Z': 'Gonini Air Servic', '5U': 'Skagway Air Services', '5T': 'Airlink Airline Ltd', 'BN': 'Landair Intl Airlines', 'BO': 'Bouraq Airlines', '5Q': 'Skaergaardsflyget', '5P': 'Ptarmigan Airways', 'BJ': 'Aviation Commercial', '5R': 'Aero Service', '5M': 'Joint Stock Company Siat', '5L': 'Aerosur', 'BV': 'Sun Air', 'BW': 'Bwia International', 'BP': 'Air Botswana Corp', 'BQ': 'Virgin Express', 'BR': 'Eva Airways Corp', 'BS': 'British International', '5E': 'Base Regional Airlines', '5D': 'Air Company Donbass Airline', '5F': 'Bonaire Airways', 'BX': 'Coast Air', 'BY': 'Britannia Airways', 'BZ': 'Keystone Air Service', '5B': 'Tie Aviation Inc', 'IJ': 'Air Libert\xe9', 'FX': 'Fedex', 'IR': 'Iran Air', 'A2': 'Intersomal', '5H': 'Odinair', 'S2': 'Sahara India Airlines', 'TJ': 'TAS Airways', 'TK': 'Turkish Airlines', 'A7': 'Air Twenty One', 'TI': 'Baltic Intl Airlines', 'IM': 'Carib Express Ltd', 'A9': 'Aircompany Airzena', 'TG': 'Thai Airways Intl', 'R9': 'Air Charter', 'OO': 'Sky West Airlines', 'ON': 'Air Nauru', 'OM': 'Miat Mongolian Airlines', 'OL': 'OLT Ostfriesische Lufttransport', 'OK': 'Czech Airlines', 'OJ': 'Air St Barthelemy', 'OI': 'Aspiring Air Services', 'OH': 'Comair', 'OG': 'Austrian Airtransport', 'OF': 'Trav Aeriens Madagascar', 'IL': 'Istanbul Airlines', 'OD': 'Zuliana de Aviaci', 'OC': 'Aviacion del Noroeste SA', 'OB': 'Shepparton Airlines', 'OA': 'Olympic Airways', 'B4': 'Bhoja Airlines Ltd', 'B6': 'Top Air Havacilik Sanayi', 'B7': 'Uni Airways Corp', 'OZ': 'Asiana Airlines', 'B2': 'Belavia', 'B3': 'Bellview Airlines Ltd', 'OW': 'Metavia Airlines', 'OV': 'Estonian Air', 'OU': 'Croatia Airlines', 'OT': 'Avant Airlines', 'B8': 'Italair', 'OE': 'Westair Commuter Airline', 'OQ': 'Zambian Express Airways', 'OP': 'Pan Am Air Bridge', 'HZ': 'Euroflight Sweden AB', 'HX': 'Hamburg Airlines', 'HY': 'Uzbekistan Airways', 'U9': 'Selcon Airlines Ltd', 'U5': 'International Business Air', 'HS': 'Highland Air AB', 'U7': 'United Aviation', 'HQ': 'Business Express', 'HV': 'Transavia Airlines', 'HW': 'North Wright Air', 'HT': 'Airwork', 'HU': 'Antigua Paradise Airways', 'HJ': 'Holmstroem Air Sweden', 'HK': 'Swan Airlines', 'HH': 'Islandsflug', 'HI': 'Papillon Airways', 'HN': 'Klm City Hopper', 'HO': 'Airways International', 'HM': 'Air Seychelles', 'HB': 'Augusta Airways', 'HC': 'Naske Air', 'HA': 'Hawaiian Airlines', 'HF': 'Hapag Lloyd', 'HG': 'Harbor Airlines', 'HD': 'New York Helicopter Corp', 'HE': 'Lgw Luftfahrtges Walter', 'AU': 'Austral Lineas Aereas', 'AG': 'Provincial Airlines', 'AF': 'Air France', '4E': 'Tanana Air Service', 'AI': 'Air India', 'AH': 'Air Algerie', 'AK': 'Airasia Sdn Bhd', 'AJ': 'Air Belgium', 'IA': 'Iraqi Airways', 'OY': 'African Intercontinental', 'IU': 'Air Straubing', 'T2': 'Taba Transportes Aereos', 'OX': 'Orient Express Air', 'AL': 'Astral aviation', '4P': 'Transportes aereos', 'H3': 'Harbour Air Ltd', '4Q': 'Trans North Aviation Ltd', 'AQ': 'Aloha Airlines', 'H8': 'Khabarovsk Aviation', 'H9': 'Blade Helicopters', 'UY': 'Cameroon Airlines', 'UX': 'Air Europa', 'UZ': 'UP Air', 'H2': 'City Bird', 'OS': 'Austrian Airlines', 'UW': 'Perimeter Airlines', 'UV': 'Helicopteros del Sureste', 'H6': 'Hageland Aviation', 'UP': 'Bahamasair', 'H4': 'Hainan Airlines', 'UR': 'British International Helicopters', 'UM': 'Air Zimbabwe', 'UL': 'Airlanka Ltd', 'UO': 'Northern Star Airlines', 'UN': 'Transaero Airlines', 'UI': 'Alaska Seaplane Service', 'UH': 'Corp Airlines Canberra', 'UK': 'Air UK Ltd', 'UJ': 'Aerosanta Airlines', 'UE': 'Transeuropean Airlines', 'UD': 'HEX Air', 'UG': 'Tuninter', 'UF': 'Turkestan Airlines', 'UA': 'United Airlines', 'UC': 'Ladeco Airlines', 'UB': 'Myanmar Airways Intl', '4F': 'Air City', '4G': 'Shenzhen Airlines', 'NH': 'All Nippon Airways', 'NI': 'Portugalia', 'NJ': 'Vanguard Airlines Inc', 'NK': 'Spirit Airlines', 'NL': 'Shaheen Air', 'NM': 'Mount Cook Airline', 'NN': 'Cardinal Airlines Ltd', 'NO': 'AUS Air', 'NA': 'Executive Airlines', 'NB': 'Sterling Airways', 'NC': 'National Jet Systems Pty', 'ND': 'Airlink Pty Ltd', 'NE': 'Knight Air', 'NF': 'Air Vanuata', 'NG': 'Lauda Air', 'NX': 'Air Macau Company Ltd', 'NY': 'Air Iceland', 'NZ': 'Air New Zealand Ltd', 'JK': 'Spanair', 'U4': 'Noman', 'NP': 'Skytrans', 'NQ': 'Orbi Georgian Air', 'NR': 'Norontair', 'NS': 'Cape York Air', 'NT': 'Binter Canarias', 'NU': 'Japan Transocean Air Co', 'NV': 'Nwt Air', 'NW': 'Northwest Airlines', 'JW': 'Pacific Eagle Airlines', 'U6': 'Ural Airlines', 'VN': 'Vietnam Airlines', 'N8': 'Expresso Aero', 'N9': 'North Coast Aviation Pty', 'U3': 'Travelair', 'N2': 'Aerolineas Internacional', 'U2': 'Easyjet Airline Company Ltd', 'N4': 'National Airlines Chile', 'N5': 'Sardairline Soc Coop Airline', 'N6': 'Aero Continente', 'N7': 'Nordic East Airways Ab', '7H': 'Era Aviation', 'TZ': 'American Trans Air', 'TX': 'Ste Nlle Air Guadeloupe', 'TY': 'Air Caledonie', 'TV': 'Haiti Trans Air S.A.', 'TW': 'Trans World Airlines Inc', 'TT': 'Air Lithuania', 'TU': 'Tunis Air', 'TR': 'Transbrasil', 'TS': 'Samoa Aviation', 'TP': 'TAP Air Portugal', 'TQ': 'Transwede Airways', 'TN': 'Australian Airlines', 'TO': 'Alkan Air', 'TL': 'Airnorth Regional', 'TM': 'LAM Mozambique', 'A5': 'Air East Limited', 'A4': 'Southern Winds', 'TH': 'Euroair', 'A6': 'Asia Pacific Airlines', 'TF': 'Air Transport Pyrenees', 'A8': 'Aerolineas Paraguayas', 'TD': 'TNT Sava', 'TE': 'Lithuanian Airlines', 'TB': 'Shuttle Inc', 'TC': 'Air Tanzania Corp', 'T4': 'Transeast Airlines', 'TA': 'Taca Intl Airlines', 'AA': 'American Airlines', 'AC': 'Air Canada', 'AB': 'Air Berlin', 'AE': 'Mandarin Airlines', 'AD': 'Aspen Mountain Air', '4X': "F'airlines B.V.", 'T9': 'Master Aviation', 'T6': 'Tavrey Aircompany', 'T7': 'Air Trans Ireland Services', '4T': 'Russian Airlines', '4U': 'Dorado Air SA', 'AM': 'Aeromexico', '4S': 'East West Airline', 'AO': 'Aviaco', 'AN': 'Ansett', '4N': 'Air North', 'AP': 'Air One', 'AS': 'Alaska Airlines', '4M': 'Minskavia', '4J': 'Love Air', '4K': 'Kenn Borek Air', 'AW': 'P.T. Dirgantara Air Service', 'AV': 'Avianca', 'AY': 'Finnair', 'AX': 'Binter Mediterraneo', '4D': 'Air Sinai', 'AZ': 'Alitalia', '4B': 'Olson Air Service', '4C': 'Aires', '4A': 'Thunderbird', 'QJ': 'Jet Airways Inc', 'D2': 'Skyline Nepc Ltd', 'D3': 'Daallo Airlines', 'QG': 'Prima Air'}
