#!/usr/bin/env python
# coding: utf-8
#
#       Copyright 2008 Olivier Berten <olivier.berten@gmail.com>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#


from swatchbook.codecs import *

class xara_jcw(SBCodec):
	"""Xara Color Palette"""
	ext = ('jcw',)
	@staticmethod
	def test(file):
		file = open(file,'rb')
		data = file.read(4)
		file.close()
		if struct.unpack('4s', data)[0] == 'JCW\x01':
			return True
		else:
			return False

	@staticmethod
	def read(swatchbook,file):
		pantone = {'P4CPC': 'PANTONE® process coated', 'P4CPCE': 'PANTONE® process coated EURO', 'P4CPU': 'PANTONE® process uncoated', 'P4CPUE': 'PANTONE® process uncoated EURO', 'PCBC': 'PANTONE® color bridge CMYK PC', 'PCBCE': 'PANTONE® color bridge CMYK EC', 'PCBU': 'PANTONE® color bridge CMYK UP', 'PFGC': 'PANTONE® solid coated', 'PFGM': 'PANTONE® solid matte', 'PFGU': 'PANTONE® solid uncoated', 'PMC': 'PANTONE® metallic coated', 'PPC': 'PANTONE® pastel coated', 'PPU': 'PANTONE® pastel uncoated'}
		if os.path.splitext(os.path.basename(file))[0] in pantone:
			swatchbook.info.title = pantone[os.path.splitext(os.path.basename(file))[0]]
		file = open(file,'rb')
		signature,version,nbcolors,type,namesize = struct.unpack('<3s B H 2B',file.read(8))
		for i in range(nbcolors):
			item = Color(swatchbook)
			A,B,C,D,ColorName = struct.unpack('<4H '+str(namesize)+'s',file.read(8+namesize))
			if type % 2:
				item.usage.add('spot')
			id = str(ColorName.split('\x00')[0],'iso-8859-1')
			if type % 16 < 8:
				id = "PANTONE "+id
			if type % 8 in (0,1):
				item.values[('CMYK',False)] = [A/10000,B/10000,C/10000,D/10000]
			elif type % 8 in (2,3):
				item.values[('RGB',False)] = [A/10000,B/10000,C/10000]
			elif type % 8 in (4,5):
				item.values[('HSV',False)] = [A/10000,B/10000,C/10000]
			if id in swatchbook.materials:
				if item.values[list(item.values.keys())[0]] == swatchbook.materials[id].values[list(swatchbook.materials[id].values.keys())[0]]:
					swatchbook.book.items.append(Swatch(id))
					continue
				else:
					sys.stderr.write('duplicated id: '+id+'\n')
					item.info.title = id
					id = id+idfromvals(item.values[list(item.values.keys())[0]])
			item.info.identifier = id
			swatchbook.materials[id] = item
			swatchbook.book.items.append(Swatch(id))
		file.close()

