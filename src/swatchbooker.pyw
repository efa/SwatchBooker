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

from __future__ import division
import re
import tempfile
from shutil import copy2
from functools import cmp_to_key
from PIL import ImageQt

from sbcommon import *

NUM_RE = re.compile('([0-9]+)')

availables_lang = {'de': u'Deutsch',
                   'en': u'English',
                   'es': u'Español',
                   'fr': u'Français',
                   'pl': u'Polski',
                   'pt_BR': u'Português do Brasil',
                   'ru': u'Русский',
                   'uk': u'Українська'}

current_sp = False
breaks = []

# 0: float, 1: percentage, 2: degrees
models = SortedDict()
models['sRGB'] = (('R', 1), ('G', 1), ('B', 1))
models['Lab'] = (('L', 0), ('a', 0), ('b', 0))
models['LCH'] = (('L', 0), ('C', 0), ('H', 0))
models['XYZ'] = (('X', 0), ('Y', 0), ('Z', 0))
models['xyY'] = (('x', 0), ('y', 0), ('Y', 0))
models['RGB'] = (('R', 1), ('G', 1), ('B', 1))
models['CMY'] = (('C', 1), ('M', 1), ('Y', 1))
models['HLS'] = (('H', 2), ('L', 1), ('S', 1))
models['HSV'] = (('H', 2), ('S', 1), ('V', 1))
models['CMYK'] = (('C', 1), ('M', 1), ('Y', 1), ('K', 1))
models['GRAY'] = (('K', 1),)
models['YIQ'] = (('Y', 0), ('I', 0), ('Q', 0))

def swupdate(id):
	form.materials[id][0].update()
	for sw in form.materials[id][1]:
		sw.update()
	for sw in form.materials[id][2]:
		sw.update()

def grupdate(item):
	form.groups[item][0].update()

class MainWindow(QMainWindow):
	def __init__(self, file=False, parent=None):
		super(MainWindow, self).__init__(parent)

		self.setWindowTitle(_('SwatchBooker Editor'))
		self.setWindowIcon(QIcon(":/swatchbooker.svg"))

		self.loadingDlg = LoadingDlg(self)
		self.fileMenu = self.menuBar().addMenu(_("&File"))
		viewMenu = self.menuBar().addMenu(_("&View"))
		viewActionGroup = QActionGroup(self)
		self.treeViewAction = QAction(_("Tree view"), self)
		self.treeViewAction.setActionGroup(viewActionGroup)
		self.treeViewAction.setCheckable(True)
		self.treeViewAction.triggered.connect(self.dispPane)
		self.gridViewAction = QAction(_("Grid view"), self)
		self.gridViewAction.setActionGroup(viewActionGroup)
		self.gridViewAction.setCheckable(True)
		self.gridViewAction.triggered.connect(self.dispPane)
		self.directionMenu = QMenu(_("Grid direction"))
		directionActionGroup = QActionGroup(self)
		self.gridVertAction = QAction(_("Vertical"), self)
		self.gridVertAction.setActionGroup(directionActionGroup)
		self.gridVertAction.setCheckable(True)
		self.gridVertAction.triggered.connect(self.gridEdit)
		self.gridHorizAction = QAction(_("Horizontal"), self)
		self.gridHorizAction.setActionGroup(directionActionGroup)
		self.gridHorizAction.setCheckable(True)
		self.gridHorizAction.triggered.connect(self.gridEdit)
		self.availMaterialsAction = QAction(_("Available materials"), self)
		self.availMaterialsAction.setCheckable(True)
		self.availMaterialsAction.triggered.connect(self.dispPane)
		viewMenu.addAction(self.treeViewAction)
		viewMenu.addAction(self.gridViewAction)
		viewMenu.addMenu(self.directionMenu)
		self.directionMenu.addAction(self.gridVertAction)
		self.directionMenu.addAction(self.gridHorizAction)
		viewMenu.addSeparator()
		viewMenu.addAction(self.availMaterialsAction)
		self.menuBar().addAction(_("Settings"), self.settings)
		self.menuBar().addAction(_("&About"), self.about)
		self.updateFileMenu()

		if settings.contains('gridView') and bool(settings.value('gridView')):
			self.gridViewAction.setChecked(True)
			self.directionMenu.setEnabled(True)
		else:
			self.treeViewAction.setChecked(True)
			self.directionMenu.setEnabled(False)
		if settings.contains('materialList') and bool(settings.value('materialList')):
			self.availMaterialsAction.setChecked(True)
		else:
			self.availMaterialsAction.setChecked(False)

		breaks = []
		self.iconsLoading = 0
		self.materials = {}
		self.profiles = {}
		self.groups = {}
		self.items = {}
		self.sb = SwatchBook()
		self.filename = False
		self.codec = 'sbz'

		if file:
			self.loadFile(file)

		self.mainWidget = QSplitter(Qt.Horizontal)
		self.mainWidget.setContentsMargins(self.mainWidget.handleWidth(), 0, self.mainWidget.handleWidth(), 0)

		groupBoxInfo = QGroupBox(_("Information"))
		self.sbInfo = InfoWidget(self.sb, self)
		infoScrollArea = QScrollArea()
		infoScrollArea.setWidget(self.sbInfo)
		infoScrollArea.setWidgetResizable(True)
		palette = infoScrollArea.viewport().palette()
		palette.setColor(QPalette.Window, Qt.transparent)
		infoScrollArea.viewport().setPalette(palette)
		infoScrollArea.setFrameShape(QFrame.NoFrame)
		sbInfoLayout = QVBoxLayout()
		sbInfoLayout.addWidget(infoScrollArea)
		groupBoxInfo.setLayout(sbInfoLayout)

		groupBoxProfiles = QGroupBox(_("Color profiles"))
		self.sbProfList = QTableWidget()
		self.sbProfList.horizontalHeader().setStretchLastSection(True)
		self.sbProfList.verticalHeader().hide()
		self.sbProfList.horizontalHeader().hide()
		self.sbProfList.setColumnCount(2)
		self.sbProfList.setColumnHidden(1, True)
		self.sbProfList.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.butProf = MenuButton(self)
		self.menuProf = QMenu()
		self.menuProf.addAction(_('Add'), self.addProfile)
		self.profRemoveAction = self.menuProf.addAction(_('Remove'), self.remProfile)
		self.butProf.setMenu(self.menuProf)
		self.profRemoveAction.setEnabled(False)

		sbProfiles = QHBoxLayout()
		sbProfiles.addWidget(self.sbProfList)
		sbProfiles.addWidget(self.butProf, 0, Qt.AlignTop)
		groupBoxProfiles.setLayout(sbProfiles)

		sbLeftPane = QSplitter(Qt.Vertical)
		sbLeftPane.addWidget(groupBoxInfo)
		sbLeftPane.addWidget(groupBoxProfiles)

		# matList
		self.groupBoxList = QGroupBox(_("Available materials"))

		self.matList = matListWidget()
		self.matNbLabel = QLabel()
		self.matListEditBut = MenuButton(self)
		self.matListEditMenu = QMenu()
		self.matListEditMenu.addAction(_('Add Color'), self.addColor)
		self.matListEditMenu.addAction(_('Add Gradient'), self.addGradient)
		self.matListEditMenu.addAction(_('Add Pattern(s)'), self.addPatterns)
		self.deleteMaterialAction = self.matListEditMenu.addAction(_('Delete'), self.deleteMaterial)
		self.matListEditMenu.addAction(_('Delete unused materials'), self.deleteUnusedMaterials)
		self.matListEditBut.setMenu(self.matListEditMenu)
		self.deleteMaterialAction.setEnabled(False)

		sbList = QGridLayout()
		sbList.addWidget(self.matList, 0, 0)
		sbList.addWidget(self.matNbLabel, 1, 0)
		sbList.addWidget(self.matListEditBut, 0, 1, Qt.AlignTop)
		self.groupBoxList.setLayout(sbList)

		# sbTree
		self.groupBoxTree = QGroupBox(_("Tree view"))

		self.treeWidget = sbTreeWidget()
		self.swNbLabel = QLabel()
		self.swTEditBut = MenuButton(self)
		self.swTEditMenu = QMenu()
		self.swTEditMenu.addAction(_('Add Color'), self.addColorSwatch)
		self.swTEditMenu.addAction(_('Add Gradient'), self.addGradientSwatch)
		self.swTEditMenu.addAction(_('Add Pattern(s)'), self.addPatternsSwatch)
		self.swTEditMenu.addAction(_('Add Spacer'), self.addSpacer)
		self.swTEditMenu.addAction(_('Add Break'), self.addBreak)
		self.swTEditMenu.addAction(_('Add Group'), self.addGroup)
		self.deleteAction = self.swTEditMenu.addAction(_('Delete'), self.delete)
		self.deleteAction.setShortcut(Qt.Key_Delete)
		self.swTEditBut.setMenu(self.swTEditMenu)
		self.deleteAction.setEnabled(False)

		sbTree = QGridLayout()
		sbTree.addWidget(self.treeWidget, 0, 0)
		sbTree.addWidget(self.swNbLabel, 1, 0)
		sbTree.addWidget(self.swTEditBut, 0, 1, Qt.AlignTop)
		self.groupBoxTree.setLayout(sbTree)

		# sbGrid
		self.groupBoxGrid = QGroupBox(_("Grid view"))

		self.gridWidget = sbGridWidget()
		self.colsLabel = QLabel()
		self.cols = QSpinBox()
		self.cols.setRange(0, 64)
		self.rowsLabel = QLabel()
		self.rows = QSpinBox()
		self.rows.setRange(0, 64)

		self.swGEditBut = MenuButton(self)
		self.swGEditMenu = QMenu()
		self.swGEditMenu.addAction(_('Add Color'), self.addColorSwatch)
		self.swGEditMenu.addAction(_('Add Gradient'), self.addGradientSwatch)
		self.swGEditMenu.addAction(_('Add Pattern(s)'), self.addPatternsSwatch)
		self.swGEditMenu.addAction(_('Add Spacer'), self.addSpacer)
		self.swGEditMenu.addAction(_('Add Break'), self.addBreak)
		self.swGEditMenu.addAction(self.deleteAction)
		self.swGEditBut.setMenu(self.swGEditMenu)

		sbGrid = QGridLayout()
		sbGrid.addWidget(self.gridWidget, 0, 0, 1, 2)
		sbGrid.setRowStretch(0, 999)
		sbGrid.setRowStretch(1, 1)
		sbGrid.addWidget(self.colsLabel, 2, 0)
		sbGrid.addWidget(self.cols, 2, 1)
		sbGrid.addWidget(self.rowsLabel, 3, 0)
		sbGrid.addWidget(self.rows, 3, 1)
		sbGrid.addWidget(self.swGEditBut, 0, 2, Qt.AlignTop)
		self.groupBoxGrid.setLayout(sbGrid)

		if settings.contains('gridHoriz') and bool(settings.value('gridHoriz')):
			self.gridHorizAction.setChecked(True)
			self.colsLabel.setText(_("Rows:"))
			self.rowsLabel.setText(_("Columns:"))
		else:
			self.gridVertAction.setChecked(True)
			self.colsLabel.setText(_("Columns:"))
			self.rowsLabel.setText(_("Rows:"))

		self.mainWidget.addWidget(sbLeftPane)
		self.mainWidget.addWidget(self.groupBoxTree)
		self.mainWidget.addWidget(self.groupBoxGrid)
		self.mainWidget.addWidget(self.groupBoxList)

		self.setCentralWidget(self.mainWidget)

		self.updSwatchCount()

		self.cols.valueChanged[int].connect(self.gridEdit)
		self.rows.valueChanged[int].connect(self.gridEdit)
		self.matList.itemSelectionChanged.connect(self.sw_display_list)
		self.treeWidget.itemSelectionChanged.connect(self.sw_display_tree)
		self.gridWidget.itemSelectionChanged.connect(self.sw_display_grid)
		self.sbProfList.itemSelectionChanged.connect(self.prof_editable)

	def clear(self):
		global breaks
		breaks = []
		self.materials = {}
		self.profiles = {}
		self.groups = {}
		self.items = {}
		self.sb = SwatchBook()

		self.sbInfo.clear()
		self.sbProfList.clear()
		self.sbProfList.setRowCount(0)
		self.matList.clear()
		self.rows.setValue(0)
		self.cols.setValue(0)
		self.gridWidget.clear()
		self.treeWidget.clear()
		self.updSwatchCount()
		self.deleteAction.setEnabled(False)
		if hasattr(self, 'editWidget'):
			self.editWidget.setParent(None)

	def sw_display_list(self):
		if self.matList.selectedItems() and (self.matList.hasFocus() or app.focusWidget() == None):
			listItem = self.matList.selectedItems()[0]
			if hasattr(self, 'editWidget'):
				self.editWidget.setParent(None)
			self.editWidget = MaterialWidget(listItem.id, self)
			self.mainWidget.addWidget(self.editWidget)
			self.treeWidget.setCurrentItem(None)
			self.gridWidget.setCurrentItem(None)
			self.deleteMaterialAction.setEnabled(True)

	def sw_display_tree(self):
		if self.treeWidget.selectedItems():
			treeItem = self.treeWidget.selectedItems()[0]
			if treeItem and isinstance(treeItem, treeItemSwatch):
				self.gridWidget.setCurrentItem(self.items[treeItem])
				self.matList.setCurrentItem(self.materials[treeItem.item.material][0])
			else:
				self.gridWidget.setCurrentItem(None)
				self.matList.setCurrentItem(None)
			if hasattr(self, 'editWidget'):
				self.editWidget.setParent(None)
			if isinstance(treeItem, treeItemSwatch):
				self.editWidget = MaterialWidget(treeItem.item.material, self)
			if isinstance(treeItem, treeItemGroup):
				self.editWidget = GroupWidget(treeItem.item, self)
			if treeItem.__class__.__name__ not in ('treeItemSpacer', 'treeItemBreak', 'noChild'):
				self.mainWidget.addWidget(self.editWidget)
			if isinstance(treeItem, noChild):
				self.deleteAction.setEnabled(False)
			else:
				self.deleteAction.setEnabled(True)

	def sw_display_grid(self):
		if self.gridWidget.selectedItems():
			gridItem = self.gridWidget.selectedItems()[0]
			items = dict([v, k] for k, v in self.items.iteritems())
			self.treeWidget.setCurrentItem(items[gridItem])
			self.matList.setCurrentItem(self.materials[gridItem.item.material][0])

	def gridEdit(self):
		if self.sender() == self.cols:
			if self.cols.value() > 0:
				self.sb.book.display['columns'] = self.cols.value()
			elif self.cols.value() == 0:
				self.sb.book.display['columns'] = False
		if self.sender() == self.rows:
			if self.rows.value() > 0:
				self.sb.book.display['rows'] = self.rows.value()
			elif self.rows.value() == 0:
				self.sb.book.display['rows'] = False
		if self.gridHorizAction.isChecked():
			settings.setValue("gridHoriz", True)
			self.colsLabel.setText(_("Rows:"))
			self.rowsLabel.setText(_("Columns:"))
		if self.gridVertAction.isChecked():
			settings.setValue("gridHoriz", False)
			self.colsLabel.setText(_("Columns:"))
			self.rowsLabel.setText(_("Rows:"))
		self.gridWidget.update()

	def updSwatchCount(self):
		usedMaterials = 0
		for id in self.materials.keys():
			if len(self.materials[id][1]) > 0:
				usedMaterials += 1
		swatchCount = self.sb.book.count(True)
		self.matNbLabel.setText(n_('%s material', '%s materials', len(self.materials)) % len(self.materials) + " (" + n_('%s used', '%s used', usedMaterials) % usedMaterials + ")")
		self.swNbLabel.setText(n_('%s swatch', '%s swatches', swatchCount) % swatchCount + " (" + n_('%s duplicate', '%s duplicates', (swatchCount - usedMaterials)) % (swatchCount - usedMaterials) + ")")

	def addMaterial(self, id):
		listItemMaterial(id)

	def addColor(self):
		id = _('New Color')
		if id in form.sb.materials:
			i = 1
			while id in form.sb.materials:
				id = _('New Color') + ' (' + str(i) + ')'
				i += 1
		material = Color(self.sb)
		material.info.identifier = id
		form.sb.materials[id] = material
		self.addMaterial(id)
		icon = self.drawIcon(id)
		self.addIcon(id, icon[0], icon[1])
		self.matList.setFocus()
		self.matList.setCurrentItem(self.materials[id][0])
		self.updSwatchCount()
		return [id]

	def addGradient(self):
		id = _('New Gradient')
		if id in form.sb.materials:
			i = 1
			while id in form.sb.materials:
				id = _('New Gradient') + ' (' + str(i) + ')'
				i += 1
		material = Gradient(form.sb)
		stop0 = ColorStop()
		stop0.position = 0
		material.colorstops.append(stop0)
		material.info.identifier = id
		form.sb.materials[id] = material
		self.addMaterial(id)
		icon = self.drawIcon(id)
		self.addIcon(id, icon[0], icon[1])
		self.matList.setFocus()
		self.matList.setCurrentItem(self.materials[id][0])
		self.updSwatchCount()
		return [id]

	def addPattern(self, fname):
		try:
			image = Image.open(fname)
			image.load()
		except (IOError, TypeError):
			goon = QMessageBox.warning(self, _("Warning"), _("This file isn't supported by the Python Image Library. Add anyway?"), QMessageBox.Yes | QMessageBox.No)
			if goon == QMessageBox.Yes:
				pass
			else:
				return
		id = os.path.basename(fname)
		patdir = os.path.join(self.sb.tmpdir, "patterns")
		if not os.path.isdir(patdir):
			os.mkdir(patdir)
		copy2(fname, patdir)
		material = Pattern(self.sb)
		material.info.identifier = id
		if material.image() and "title" in material.image().info:
			material.info.title = material.image().info["title"]
		else:
			material.info.title = os.path.splitext(id)[0]
		form.sb.materials[id] = material
		self.addMaterial(id)
		icon = self.drawIcon(id)
		self.addIcon(id, icon[0], icon[1])
		self.matList.setFocus()
		self.matList.setCurrentItem(self.materials[id][0])
		self.updSwatchCount()
		return id

	def addPatterns(self):
		Image.init()
		supported = " ("
		for ext in Image.EXTENSION:
			if Image.EXTENSION[ext] in Image.ID:
				supported += " *" + ext
		supported += ")"
		dir = settings.value('lastPatternDir') if settings.contains('lastPatternDir') else QDir.homePath()
		fnames = QFileDialog.getOpenFileNames(self,
							_("Choose image file"), dir,
							(_("Supported image files") + supported))[0]
		if len(fnames) > 0:
			settings.setValue('lastPatternDir', os.path.dirname(fnames[0]))
			ids = []
			for fname in fnames:
				id = self.addPattern(fname)
				if id:
					ids.append(id)
			return ids

	def deleteMaterial(self):
		#TODO: deal with Gradients, DerivedPatterns, etc. using that material
		item = self.matList.selectedItems()[0]
		for treeItem in self.materials[item.id][1]:
			if treeItem.parent():
				treeItem.parent().takeChild(treeItem.parent().indexOfChild(treeItem))
			else:
				self.treeWidget.takeTopLevelItem(self.treeWidget.indexOfTopLevelItem(treeItem))
		treeItem = None
		for gridItem in self.materials[item.id][2]:
			self.gridWidget.takeItem(self.gridWidget.row(gridItem))
		gridItem = None
		if hasattr(self, 'editWidget'):
			self.editWidget.setParent(None)
		self.matList.takeItem(self.matList.row(item))
		if isinstance(self.sb.materials[item.id], Pattern):
			self.sb.materials[item.id].deleteFile()
		del self.sb.materials[item.id]
		del self.materials[item.id]
		self.deleteAction.setEnabled(False)
		self.updSwatchCount()

	def deleteUnusedMaterials(self):
		for material in self.sb.materials.keys():
			if len(self.materials[material][1]) == 0:
				self.matList.takeItem(self.matList.row(self.materials[material][0]))
				del self.sb.materials[material]
				del self.materials[material]
		self.updSwatchCount()

	def addColorSwatch(self):
		self.addSwatch('Color')

	def addGradientSwatch(self):
		self.addSwatch('Gradient')

	def addPatternsSwatch(self):
		self.addSwatch('Patterns')

	def addSwatch(self, type):
		selected = self.treeWidget.selectedItems()
		ids = eval('self.add' + type + '()')
		for id in ids:
			item = Swatch(id)
			icon = self.drawIcon(id)
			self.addIcon(id, icon[0], icon[1])
			gridItem = gridItemSwatch(item)
			treeItem = treeItemSwatch(item)
			if selected:
				selTItem = selected[0]
				if selTItem.parent():
					parent = selTItem.parent().item
					if isinstance(selTItem, noChild):
						index = 0
					else:
						index = selTItem.parent().indexOfChild(selTItem) + 1
				else:
					parent = form.sb.book
					index = self.treeWidget.indexOfTopLevelItem(selTItem) + 1
				parent.items.insert(index, item)
	
				if selTItem.parent() == None:
					tIndex = self.treeWidget.indexOfTopLevelItem(selTItem)
					self.treeWidget.insertTopLevelItem(tIndex + 1, treeItem)
				else:
					tIndex = selTItem.parent().indexOfChild(selTItem)
					selTItem.parent().insertChild(tIndex + 1, treeItem)
	
				if isinstance(selTItem, treeItemGroup):
					selLItem = self.groups[selTItem.item][1][1]
				elif isinstance(selTItem, noChild):
					selLItem = self.groups[selTItem.parent().item][1][0]
				else:
					selLItem = self.items[selTItem]
				lIndex = self.gridWidget.indexFromItem(selLItem).row()
				self.gridWidget.insertItem(lIndex + 1, gridItem)
				if isinstance(selTItem, noChild):
					selTItem.parent().takeChild(0)
			else:
				self.sb.book.items.append(item)
				self.treeWidget.addTopLevelItem(treeItem)
				self.gridWidget.addItem(gridItem)
			self.items[treeItem] = gridItem
			selected = [treeItem]
		if len(ids) > 0:
			self.treeWidget.setCurrentItem(treeItem)
			self.gridWidget.update()
			self.updSwatchCount()

	def addBreak(self):
		self.addBreakSpacer('Break')

	def addSpacer(self):
		self.addBreakSpacer('Spacer')

	def addBreakSpacer(self, type):
		item = eval(type + '()')
		gridItem = eval('gridItem' + type + '(item)')
		treeItem = eval('treeItem' + type + '(item)')
		if self.treeWidget.selectedItems():
			selTItem = self.treeWidget.selectedItems()[0]
			if selTItem.parent():
				parent = selTItem.parent().item
				if isinstance(selTItem, noChild):
					index = 0
				else:
					index = selTItem.parent().indexOfChild(selTItem) + 1
			else:
				parent = form.sb.book
				index = self.treeWidget.indexOfTopLevelItem(selTItem) + 1
			parent.items.insert(index, item)

			if selTItem.parent() == None:
				tIndex = self.treeWidget.indexOfTopLevelItem(selTItem)
				self.treeWidget.insertTopLevelItem(tIndex + 1, treeItem)
			else:
				tIndex = selTItem.parent().indexOfChild(selTItem)
				selTItem.parent().insertChild(tIndex + 1, treeItem)

			if isinstance(selTItem, treeItemGroup):
				selLItem = self.groups[selTItem.item][1][1]
			elif isinstance(selTItem, noChild):
				selLItem = self.groups[selTItem.parent().item][1][0]
			else:
				selLItem = self.items[selTItem]
			lIndex = self.gridWidget.indexFromItem(selLItem).row()
			self.gridWidget.insertItem(lIndex + 1, gridItem)
			if isinstance(selTItem, noChild):
				selTItem.parent().takeChild(0)
		else:
			self.sb.book.items.append(item)
			self.treeWidget.addTopLevelItem(treeItem)
			self.gridWidget.addItem(gridItem)
		self.items[treeItem] = gridItem
		self.treeWidget.setCurrentItem(treeItem)
		self.gridWidget.update()

	def addGroup(self):
		item = Group()
		item.info.title = _('New group')
		treeItem = treeItemGroup(item)
		gridItemIn = gridItemGroup(item)
		gridItemOut = gridItemGroup(item)
		if self.treeWidget.selectedItems():
			selTItem = self.treeWidget.selectedItems()[0]
			if selTItem.parent():
				parent = selTItem.parent().item
				if isinstance(selTItem, noChild):
					index = 0
				else:
					index = selTItem.parent().indexOfChild(selTItem) + 1
			else:
				parent = form.sb.book
				index = self.treeWidget.indexOfTopLevelItem(selTItem) + 1
			parent.items.insert(index, item)

			if selTItem.parent() == None:
				tIndex = self.treeWidget.indexOfTopLevelItem(selTItem)
				self.treeWidget.insertTopLevelItem(tIndex + 1, treeItem)
			else:
				tIndex = selTItem.parent().indexOfChild(selTItem)
				selTItem.parent().insertChild(tIndex + 1, treeItem)

			if isinstance(selTItem, treeItemGroup):
				selLItem = self.groups[selTItem.item][1][1]
			elif isinstance(selTItem, noChild):
				selLItem = self.groups[selTItem.parent().item][1][0]
			else:
				selLItem = self.items[selTItem]
			lIndex = self.gridWidget.indexFromItem(selLItem).row()
			self.gridWidget.insertItem(lIndex + 1, gridItemOut)
			self.gridWidget.insertItem(lIndex + 1, gridItemIn)
			if isinstance(selTItem, noChild):
				selTItem.parent().takeChild(0)
		else:
			self.sb.book.items.append(item)
			self.treeWidget.addTopLevelItem(treeItem)
		self.groups[item][1] = (gridItemIn, gridItemOut)
		self.gridWidget.addItem(gridItemIn)
		self.gridWidget.addItem(gridItemOut)
		self.items[treeItem] = None
		nochild = noChild()
		treeItem.addChild(nochild)
		self.treeWidget.expandItem(treeItem)
		self.treeWidget.setCurrentItem(treeItem)
		self.gridWidget.update()

	def delete(self):
		if self.treeWidget.selectedItems():
			selTItem = self.treeWidget.selectedItems()[0]
			if isinstance(selTItem, treeItemGroup):
				self.del_group_from_list(selTItem)
			else:
				if isinstance(selTItem, treeItemSwatch):
					self.materials[selTItem.item.material][1].remove(selTItem)
					self.materials[selTItem.item.material][2].remove(self.items[selTItem])
				self.gridWidget.takeItem(self.gridWidget.row(self.items[selTItem]))
			if isinstance(selTItem, treeItemBreak):
				global breaks
				breaks.remove(self.items[selTItem])
			if selTItem.parent():
				tParent = selTItem.parent()
				tParent.takeChild(tParent.indexOfChild(selTItem))
				tParent.item.items.remove(selTItem.item)
				if tParent.childCount() == 0:
					nochild = noChild()
					tParent.addChild(nochild)
			else:
				self.treeWidget.takeTopLevelItem(self.treeWidget.indexOfTopLevelItem(selTItem))
				self.sb.book.items.remove(selTItem.item)
		if self.treeWidget.topLevelItemCount() == 0:
			self.deleteAction.setEnabled(False)
		self.updSwatchCount()
		self.gridWidget.update()

	def del_group_from_list(self, group):
		self.gridWidget.takeItem(self.gridWidget.row(self.groups[group.item][1][0]))
		self.gridWidget.takeItem(self.gridWidget.row(self.groups[group.item][1][1]))
		del self.groups[group.item]
		for i in range(group.childCount()):
			if isinstance(group.child(i), treeItemGroup):
				self.del_group_from_list(group.child(i))
			else:
				if isinstance(group.child(i), treeItemSwatch):
					self.materials[group.child(i).item.material][1].remove(group.child(i))
					self.materials[group.child(i).item.material][2].remove(self.items[group.child(i)])
				self.gridWidget.takeItem(self.gridWidget.row(self.items[group.child(i)]))
			group.item.items.remove(group.child(i).item)

	def dispPane(self):
		if self.availMaterialsAction.isChecked():
			settings.setValue("materialList", True)
			self.groupBoxList.show()
		else:
			settings.setValue("materialList", False)
			self.groupBoxList.hide()
		if self.treeViewAction.isChecked():
			settings.setValue("gridView", False)
			self.groupBoxTree.show()
			self.groupBoxGrid.hide()
			self.directionMenu.setEnabled(False)
		if self.gridViewAction.isChecked():
			settings.setValue("gridView", True)
			self.groupBoxTree.hide()
			self.groupBoxGrid.show()
			self.directionMenu.setEnabled(True)

	def about(self):
		QMessageBox.about(self, _("About SwatchBooker"),
                """<b>SwatchBooker</b> %s
                <p>&copy; 2008 Olivier Berten
                <p>Qt %s - PyQt %s""" % (
                VERSION, QT_VERSION_STR, PYQT_VERSION_STR))

	def settings(self):
		dialog = SettingsDlg(self)
		if dialog.exec_():
			if dialog.returnDisProf():
				settings.setValue("mntrProfile", dialog.returnDisProf())
			else:
				settings.remove("mntrProfile")
			if dialog.returnCMYKProf():
				settings.setValue("CMYKProfile", dialog.returnCMYKProf())
			else:
				settings.remove("CMYKProfile")
			settings.setValue("MaxRecentFiles", dialog.RecFilesSpin.value())
			if dialog.lang:
				settings.setValue("Language", dialog.lang)
			else:
				settings.remove("Language")
			self.updateFileMenu()

	def updateFileMenu(self, fname=False):
		if not settings.contains("MaxRecentFiles"):
			settings.setValue("MaxRecentFiles", 6)
		files = settings.value("recentFileList") or []
		for file in files:
			if not QFile.exists(file):
				files.remove(file)

		MaxRecentFiles = int(settings.value("MaxRecentFiles"))
		if fname:
			if fname in files:
				files.remove(fname)
			files = [fname] + files
			if len(files) > MaxRecentFiles:
				files = files[:MaxRecentFiles]

		settings.setValue("recentFileList", files)

		numRecentFiles = min(len(files), MaxRecentFiles)

		recentFileActs = []

		for h in range(MaxRecentFiles):
			recentFileActs.append(QAction(self))
			recentFileActs[h].setVisible(False)
			recentFileActs[h].triggered.connect(self.openRecentFile)

		for i in range(numRecentFiles):
			text = u"&{0} {1}".format(i + 1, self.strippedName(files[i]))
			recentFileActs[i].setText(text)
			recentFileActs[i].setData(files[i])
			recentFileActs[i].setVisible(True)

		for j in range(numRecentFiles, MaxRecentFiles):
			recentFileActs[j].setVisible(False)

		self.fileMenu.clear()
		self.fileMenu.addAction(_("&New"), self.fileNew, QKeySequence.New)
		self.fileMenu.addAction(_("&Open"), self.fileOpen, QKeySequence.Open)
		self.fileMenu.addAction(_("Open from web"), self.webOpen)
		self.fileMenu.addAction(_("&Save"), self.fileSave, QKeySequence.Save)
		self.fileMenu.addAction(_("Save As..."), self.fileSaveAs)
		self.fileMenu.addSeparator()
		for k in range(MaxRecentFiles):
			self.fileMenu.addAction(recentFileActs[k])

	def strippedName(self, fullFileName):
		return QFileInfo(fullFileName).fileName()

	def fileNew(self):
		self.sb = SwatchBook()
		self.filename = False
		self.codec = 'sbz'
		self.clear()

	def webOpen(self):
		try:
			dialog = webOpenDlg(self, settings)
			if dialog.exec_() and dialog.svc and dialog.ids:
				self.clear()
				self.loadWeb(dialog.svc, dialog.ids[0])
		except IOError:
			QMessageBox.critical(self, _('Error'), _("No internet connexion has been found"))

	def loadWeb(self, websvc, webid):
		thread = webOpenThread(websvc, webid, self)
		thread.finished.connect(self.fill)
		app.setOverrideCursor(Qt.WaitCursor)
		self.loadingDlg.label.setText(_("Loading swatch book"))
		self.loadingDlg.progress.hide()
		self.loadingDlg.show()
		thread.start()

	def fileOpen(self):
		dir = settings.value('lastOpenDir') if settings.contains('lastOpenDir') else QDir.homePath()
		filetypes = []
		for codec in codecs.reads:
			codec_exts = []
			for ext in eval('codecs.' + codec).ext:
				codec_exts.append('*.' + ext)
			codec_txt = eval('codecs.' + codec).__doc__ + ' (' + " ".join(codec_exts) + ')'
			filetypes.append(codec_txt)
		allexts = ["*.%s" % format.lower() \
				   for format in codecs.readexts.keys()]
		if settings.contains('lastOpenCodec'):
			filetype = settings.value('lastOpenCodec')
		else:
			filetype = ''
		fname, filetype = QFileDialog.getOpenFileName(self,
							_("Choose file"), dir,
							(_("All supported files (%s)") % " ".join(allexts)) + ";;" + (";;".join(sorted(filetypes))) + ";;" + _("All files (*)"), filetype)
		if fname:
			settings.setValue('lastOpenCodec', filetype)
			settings.setValue('lastOpenDir', os.path.dirname(fname))
			self.clear()
			self.loadFile(fname)

	def openRecentFile(self):
		action = self.sender()
		if action:
			self.clear()
			self.loadFile(action.data())

	def loadFile(self, fname):
		thread = fileOpenThread(os.path.realpath(fname), self)
		thread.finished.connect(self.fill)
		thread.fileFormatError.connect(self.fileFormatError)
		app.setOverrideCursor(Qt.WaitCursor)
		self.loadingDlg.label.setText(_("Loading swatch"))
		self.loadingDlg.progress.hide()
		self.loadingDlg.show()
		thread.start()

	def fill(self):
		self.sbInfo.update(self.sb)
		self.loadingDlg.label.setText(_("Filling views"))
		self.loadingDlg.progress.setMaximum(self.sb.book.count() + len(self.sb.materials))
		self.loadingDlg.progress.setValue(0)
		self.loadingDlg.progress.show()

		for prof in self.sb.profiles:
			self.addProfileToList(prof, self.sb.profiles[prof])
		if self.sb.book.display['columns']:
			self.cols.setValue(self.sb.book.display['columns'])
		if self.sb.book.display['rows']:
			self.rows.setValue(self.sb.book.display['rows'])

		if self.filename:
			self.updateFileMenu(self.filename)
		thread = fillViewsThread(self)
		thread.finished.connect(self.buildIcons)
		thread.filled.connect(self.filled)
		thread.start()

	def filled(self):
		self.loadingDlg.progress.setValue(self.loadingDlg.progress.value() + 1)

	def fileFormatError(self):
		app.restoreOverrideCursor()
		QMessageBox.critical(self, _("Error"), _("Unsupported file"))

	def buildIcons(self):
		self.updSwatchCount()
		self.loadingDlg.label.setText(_("Drawing icons"))
		self.loadingDlg.progress.setMaximum(len(self.sb.materials))
		self.loadingDlg.progress.setValue(0)
		self.loadingDlg.progress.show()
		self.treeWidget.expandAll()
		if len(self.materials) > 0:
			for id in self.materials:
				thread = drawIconThread(id, self)
				self.iconsLoading += 1
				thread.icon[str,QImage,QImage].connect(self.addIcon)
				thread.finished.connect(self.iconLoaded)
				thread.start()
		else:
			self.fullyLoaded()

	def iconLoaded(self):
		self.iconsLoading -= 1
		if self.iconsLoading == 0:
			self.fullyLoaded()

	def drawIcon(self, id):
		material = form.sb.materials[id]
		pix = QImage(16, 16, QImage.Format_ARGB32_Premultiplied)
		pix.fill(Qt.transparent)
		paint = QPainter()
		prof_out = settings.value("mntrProfile") or False
		if material.__class__.__name__ in ('Color', 'Tint', 'Tone', 'Shade') and material.toRGB8(prof_out):
			r, g, b = material.toRGB8(prof_out)
			paint.begin(pix)
			paint.setBrush(QColor(r, g, b))
			if 'spot' in material.usage:
				paint.drawEllipse(0, 0, 15, 15)
			else:
				paint.drawRect(0, 0, 15, 15)
			paint.end()
			normal = pix.copy()
			paint.begin(pix)
			paint.setPen(QColor(255, 255, 255))
			if 'spot' in material.usage:
				paint.drawEllipse(0, 0, 15, 15)
			else:
				paint.drawRect(0, 0, 15, 15)
			paint.setPen(Qt.DotLine)
			if 'spot' in material.usage:
				paint.drawEllipse(0, 0, 15, 15)
			else:
				paint.drawRect(0, 0, 15, 15)
			paint.end()
		elif isinstance(material, Pattern) and material.image():
			image = ImageQt.ImageQt(material.imageRGB())
			paint.begin(pix)
			paint.drawImage(0, 0, image.scaled(16, 16, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
			paint.setPen(QColor(0, 0, 0))
			paint.drawRect(0, 0, 15, 15)
			normal = pix.copy()
			paint.setPen(QColor(255, 255, 255))
			paint.drawRect(0, 0, 15, 15)
			paint.setPen(Qt.DotLine)
			paint.drawRect(0, 0, 15, 15)
			paint.end()
		elif isinstance(material, Gradient):
			gradient = QLinearGradient(0, 0, 1, 0)
			gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
			stops = material.colorstops
			for i, stop in enumerate(stops):
				if i > 0 and stop.position == stops[i - 1].position:
					location = stop.position + 0.0001
				else:
					location = stop.position
				try:
					c = form.sb.materials[stop.color].toRGB8(prof_out) or (218, 218, 218)
				except KeyError:
					c = (218, 218, 218)
				gradient.setColorAt(location, QColor(c[0], c[1], c[2]))
			paint.begin(pix)
			paint.setBrush(gradient)
			paint.drawRect(0, 0, 15, 15)
			paint.end()
			normal = pix.copy()
			paint.begin(pix)
			paint.setPen(QColor(255, 255, 255))
			paint.drawRect(0, 0, 15, 15)
			paint.setPen(Qt.DotLine)
			paint.drawRect(0, 0, 15, 15)
			paint.end()
		else:
			paint.begin(pix)
			paint.setPen(QPen(QColor(218, 218, 218), 3.0))
			paint.drawLine(QLine(3, 3, 12, 12))
			paint.drawLine(QLine(12, 3, 3, 12))
			paint.end()
			normal = pix.copy()
			paint.begin(pix)
			paint.setPen(QColor(255, 255, 255))
			paint.drawRect(0, 0, 15, 15)
			paint.setPen(Qt.DotLine)
			paint.drawRect(0, 0, 15, 15)
			paint.end()
		selected = pix

		return [normal, selected]

	def addIcon(self, id, normal, selected):
		if self.loadingDlg.isVisible():
			self.loadingDlg.progress.setValue(self.loadingDlg.progress.value() + 1)
		icon = QIcon(QPixmap.fromImage(normal))
		icon.addPixmap(QPixmap.fromImage(selected), QIcon.Selected)
		self.materials[id][3] = icon
		swupdate(id)

	def fullyLoaded(self):
		self.gridWidget.update()
		app.restoreOverrideCursor()
		self.loadingDlg.hide()

	def fileSave(self):
		if self.filename and self.codec:
			self.sb.write(self.codec, self.filename)
		else:
			self.fileSaveAs()

	def fileSaveAs(self):
		filetypes = {}
		for codec in codecs.writes:
			codec_exts = []
			for ext in eval('codecs.' + codec).ext:
				codec_exts.append('*.' + ext)
			codec_txt = eval('codecs.' + codec).__doc__ + ' (' + " ".join(codec_exts) + ')'
			filetypes[codec_txt] = (codec, eval('codecs.' + codec).ext[0])
		dir = settings.value('lastSaveDir') if settings.contains('lastSaveDir') else "."
		f = os.path.splitext(os.path.basename(self.filename or ''))[0]
		if f == '':
			f = self.sb.info.title
		if settings.contains('lastSaveCodec'):
			filetype = settings.value('lastSaveCodec')
		else:
			filetype = ''
		fname, filetype = QFileDialog.getSaveFileName(self,
						_("Save file"), os.path.join(dir, f),
						";;".join(filetypes.keys()), filetype)
		if fname:
			if len(fname.rsplit(".", 1)) == 1 or (len(fname.rsplit(".", 1)) > 1 and fname.rsplit(".", 1)[1] != filetypes[filetype][1]):
				fname += "." + filetypes[filetype][1]
			self.filename = fname
			settings.setValue('lastSaveDir', os.path.dirname(fname))
			settings.setValue('lastSaveCodec', filetype)
			self.codec = filetypes[filetype][0]
			self.fileSave()
			if self.codec in codecs.reads:
				self.updateFileMenu(fname)

	def prof_editable(self):
		if self.sbProfList.isItemSelected(self.sbProfList.currentItem()):
			self.profRemoveAction.setEnabled(True)

	def addProfile(self):
		fname = QFileDialog.getOpenFileName(self,
							_("Choose file"), ".",
							(_("ICC profiles (*.icc *.icm);;" + _("All files (*)"))))[0]
		if fname:
			# the next 6 lines are a workaround for the unability of lcms to deal with unicode file names
			fi = open(fname, 'rb')
			uri = tempfile.mkstemp()[1]
			fo = open(uri, 'wb')
			fo.write(fi.read())
			fi.close()
			fo.close()
			profile = icc.ICCprofile(uri)
			#TODO: check if exists
			id = os.path.basename(fname)
			self.sb.profiles[id] = profile
			self.addProfileToList(id, profile)

	def addProfileToList(self, id, profile):
			profItemID = QTableWidgetItem(id)
			profItemTitle = QTableWidgetItem(profile.info['desc'][0])
			cprt = profile.info['cprt']
			if 0 in cprt:
				profItemTitle.setToolTip(cprt[0])
			elif 'en_US' in cprt:
				profItemTitle.setToolTip(cprt['en_US'])
			row = self.sbProfList.rowCount()
			self.sbProfList.setRowCount(row + 1)
			self.sbProfList.setItem(row, 0, profItemTitle)
			self.sbProfList.setItem(row, 1, profItemID)
			space = profile.info['space'].strip()
			if space in self.profiles:
				self.profiles[space].append(id)
			else:
				self.profiles[space] = [id]

	def remProfile(self):
		profid = self.sbProfList.item(self.sbProfList.currentItem().row(), 1).text()
		self.sbProfList.removeRow(self.sbProfList.currentItem().row())
		self.profiles[self.sb.profiles[profid].info['space'].strip()].remove(profid)
		del self.sb.profiles[profid]
		self.profRemoveAction.setEnabled(False)
		#TODO: remove profile from color values

class MenuButton(QToolButton):
	def __init__(self, parent=None):
		super(MenuButton, self).__init__(parent)
		self.setFixedSize(12, 12)
		self.setArrowType(Qt.DownArrow)
		self.setStyleSheet("MenuButton::menu-indicator {image: none;}")
		self.setPopupMode(QToolButton.InstantPopup)

class InfoWidget(QWidget):
	def __init__(self, item, parent=None):
		super(InfoWidget, self).__init__(parent)
		self.item = item
		for field in Info.dc:
			if Info.dc[field][1]:
				exec('self.' + field + ' = QTextEdit()')
				exec('self.' + field + '.textChanged.connect(self.edit)')
			else:
				exec('self.' + field + ' = QLineEdit()')
				exec('self.' + field + '.editingFinished.connect(self.edit)')
			exec('self.' + field + '.setObjectName("' + field + '")')
			if Info.dc[field][0]:
				exec('self.l10n' + field.capitalize() + ' = l10nButton()')
				exec('self.l10n' + field.capitalize() + '.pressed.connect(self.l10n)')
		self.date = QDateTimeEdit()
#		self.license = LicenseWidget()
		self.license = QLineEdit()
		self.license.setObjectName('license')
		self.license.editingFinished.connect(self.edit)

		layout = QGridLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		i = 0
		if item.__class__.__name__ not in ('SwatchBook', 'Group'):
			layout.addWidget(QLabel(_("Identifier:")), i, 0)
			layout.addWidget(self.identifier, i, 1, 1, 2)
			i += 1
		layout.addWidget(QLabel(_("Title:")), i, 0)
		layout.addWidget(self.title, i, 1)
		layout.addWidget(self.l10nTitle, i, 2)
		i += 1

		layout.addWidget(QLabel(_("Description:")), i, 0, 1, 2)
		layout.addWidget(self.description, i + 1, 0, 1, 2)
		layout.addWidget(self.l10nDescription, i + 1, 2, Qt.AlignTop)
		i = i + 2

		if item.__class__.__name__ in ('SwatchBook',):
			layout.addWidget(QLabel(_("Rights:")), i, 0, 1, 2)
			layout.addWidget(self.rights, i + 1, 0, 1, 2)
			layout.addWidget(self.l10nRights, i + 1, 2, Qt.AlignTop)
			i = i + 2

			layout.addWidget(QLabel(_("License:")), i, 0)
			layout.addWidget(self.license, i, 1, 1, 2)
			i += 1

		self.setLayout(layout)
		self.update(item)

	def update(self, item):
		self.item = item
		for field in Info.dc:
			exec('self.' + field + '.setText(item.info.' + field + ')')
			if Info.dc[field][0]:
				if eval('len(item.info.' + field + '_l10n) > 0'):
					exec('self.l10n' + field.capitalize() + '.set()')
				else:
					exec('self.l10n' + field.capitalize() + '.clear()')
#		self.date.setDateTime()
		self.license.setText(item.info.license)

	def clear(self):
		for field in Info.dc:
			exec('self.' + field + '.clear()')
			if Info.dc[field][0]:
				exec('self.l10n' + field.capitalize() + '.clear()')
#		self.date.clear()
		self.license.clear()

	def edit(self):
		if self.sender().objectName() == 'identifier':
			newid = self.sender().text()
			if self.item.info.identifier != 	newid:
				if newid in form.sb.materials:
					QMessageBox.critical(self, _('Error'), _("There's already a material with that identifier."))
					self.sender().setText(self.item.info.identifier)
				else:
					form.sb.materials[newid] = form.sb.materials[self.item.info.identifier]
					del form.sb.materials[self.item.info.identifier]
					form.materials[newid] = form.materials[self.item.info.identifier]
					del form.materials[self.item.info.identifier]
					self.item.info.identifier = newid
					form.materials[newid][0].id = newid
					for sw in form.materials[newid][1]:
						sw.item.material = newid
		else:
			if isinstance(self.sender(), QTextEdit):
				text = self.sender().toPlainText()
			else:
				text = self.sender().text()
			exec('self.item.info.' + self.sender().objectName() + ' = text')
		if isinstance(self.item, Group):
			grupdate(self.item)
		elif not isinstance(self.item, SwatchBook):
			swupdate(self.item.info.identifier)
			form.matList.scrollTo(form.matList.currentIndex())

	def l10n(self):
		if not self.sender().isChecked():
			infos = {}
			for field in Info.dc:
				if Info.dc[field][0]:
					exec('infos[self.l10n' + field.capitalize() + '] = "' + field + '"')
			long = Info.dc[infos[self.sender()]][1]
			l10nPopup = l10nWidget(self.sender(), eval('self.item.info.' + infos[self.sender()] + '_l10n'), long, self)
			l10nPopup.show()

class cornerButton(QToolButton):
	def __init__(self, parent=None):
		super(cornerButton, self).__init__(parent)

class l10nButton(QToolButton):
	def __init__(self, parent=None):
		super(l10nButton, self).__init__(parent)
		self.setCheckable(True)
		self.setText('l10n')

	def set(self):
		self.setStyleSheet("l10nButton { font-size: 9px; font-weight: bold }")

	def clear(self):
		self.setStyleSheet("l10nButton { font-size: 9px; font-weight: normal }")

class l10nWidget(QWidget):
	def __init__(self, caller, info, long=False, parent=None):
		super(l10nWidget, self).__init__(parent)
		self.setWindowFlags(Qt.Popup)

		self.caller = caller
		self.info = info
		self.long = long

		list = QWidget()
		self.l10nList = QVBoxLayout()
		self.l10nList.setContentsMargins(0, 0, 0, 0)
		list.setLayout(self.l10nList)

		addButton = QPushButton(_('Add localization'))
		scrollArea = QScrollArea()
		scrollArea.setWidget(list)
		scrollArea.setContentsMargins(0, 0, 0, 0)
		scrollArea.setWidgetResizable(True)
		layout = QVBoxLayout()
		layout.addWidget(addButton)
		layout.addWidget(scrollArea)
		self.setLayout(layout)

		screen = QApplication.desktop().availableGeometry(caller)

		x = caller.mapToGlobal(QPoint(0, 0)).x() + caller.rect().width()
		y = caller.mapToGlobal(QPoint(0, 0)).y()
		sh = QSize(300, 150)

		self.resize(sh)
		if y + sh.height() > screen.height():
			y = y - sh.height() + caller.rect().height()
		if x + sh.width() > screen.width():
			x = x - caller.rect().width() - sh.width()
		self.move(QPoint(x, y))

		for lang in info:
			self.l10nList.addWidget(l10nItem(lang, info[lang], self.long, parent=self))

		addButton.clicked.connect(self.addItem)

	def addItem(self):
		self.l10nList.addWidget(l10nItem(long=self.long, parent=self))

	def paintEvent(self, e):
		p = QPainter(self)
		option = QStyleOption()
		option.initFrom(QMenu())
		option.rect = self.rect()
		self.style().drawPrimitive(QStyle.PE_PanelMenu, option, p, self)
		self.style().drawPrimitive(QStyle.PE_FrameMenu, option, p, self)

	def hideEvent(self, e):
		self.caller.setDown(False)

class l10nItem(QWidget):
	def __init__(self, lang='', text='', long=False, parent=None):
		super(l10nItem, self).__init__(parent)

		self.lang = lang
		self.text = text
		self.parent = parent

		layout = QHBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		self.langEdit = QLineEdit(lang)
		self.langEdit.setFixedWidth(50)
		if long:
			self.textEdit = QTextEdit()
		else:
			self.textEdit = QLineEdit()
		self.textEdit.setText(text)
		delLoc = QPushButton('-')
		delLoc.setFixedWidth(delLoc.sizeHint().height())
		layout.addWidget(self.langEdit, 0, Qt.AlignTop)
		layout.addWidget(self.textEdit, 0, Qt.AlignTop)
		layout.addWidget(delLoc, 0, Qt.AlignTop)
		self.setLayout(layout)

		self.langEdit.editingFinished.connect(self.langEdited)
		self.textEdit.textChanged[str].connect(self.textEdited)
		self.textEdit.textChanged.connect(self.textEdited)
		delLoc.clicked.connect(self.delLoc)

	def langEdited(self):
		if (self.langEdit.text() != self.lang) and (self.langEdit.text() not in self.parent.info) and (self.langEdit.text() > ''):
			if self.lang > '':
				del self.parent.info[self.lang]
			self.textEdited()
			self.lang = self.langEdit.text()
			self.parent.caller.set()
		else:
			self.langEdit.setText(self.lang)

	def textEdited(self):
		if isinstance(self.textEdit, QTextEdit):
			text = self.textEdit.toPlainText()
		else:
			text = self.textEdit.text()
		self.parent.info[self.langEdit.text()] = text

	def delLoc(self):
		if self.langEdit.text() > '':
			del self.parent.info[self.langEdit.text()]
		self.parent.l10nList.removeWidget(self)
		self.setParent(None)
		if self.parent.l10nList.count() == 0:
			self.parent.caller.clear()

class listItemMaterial(QListWidgetItem):
	def __init__(self, id):
		super(listItemMaterial, self).__init__(form.matList)
		self.id = id
		form.materials[id] = [self, [], [], False]
		self.update()

	def update(self):
		if form.sb.materials[self.id].info.title > '':
			text = form.sb.materials[self.id].info.title
		else:
			text = form.sb.materials[self.id].info.identifier
		self.setText(text)
		if form.materials[self.id][3]:
			self.setIcon(form.materials[self.id][3])

	@staticmethod
	def alphanum_key(s):
		if s:
			return [ int(c) if c.isdigit() else c.lower() for c in NUM_RE.split(s) ]

	def __lt__ (self, other):
		lvalue = self.alphanum_key(self.data(0))
		rvalue = self.alphanum_key(other.data(0))
		if lvalue == rvalue:
			return self.id < other.id
		else:
			return lvalue < rvalue

class gridItemSwatch(QListWidgetItem):
	def __init__(self, item, parent=None):
		super(gridItemSwatch, self).__init__(parent)
		self.item = item
		form.materials[item.material][2].append(self)
		self.setSizeHint(QSize(17, 17))
		self.update()

	def update(self):
		text = [form.sb.materials[self.item.material].info.identifier, ]
		if form.sb.materials[self.item.material].info.title > '':
			text.append(form.sb.materials[self.item.material].info.title)
		self.setToolTip('<br />'.join(text))
		if form.materials[self.item.material][3]:
			self.setIcon(form.materials[self.item.material][3])

class treeItemSwatch(QTreeWidgetItem):
	def __init__(self, item, parent=None):
		super(treeItemSwatch, self).__init__(parent)
		self.item = item
		form.materials[item.material][1].append(self)
		self.setFlags(self.flags() & ~(Qt.ItemIsDropEnabled))
		self.update()

	def update(self):
		if form.sb.materials[self.item.material].info.title > '':
			text = form.sb.materials[self.item.material].info.title
		else:
			text = form.sb.materials[self.item.material].info.identifier
		self.setText(0, text)
		if form.materials[self.item.material][3]:
			self.setIcon(0, form.materials[self.item.material][3])

class treeItemGroup(QTreeWidgetItem):
	def __init__(self, item, parent=None):
		super(treeItemGroup, self).__init__(parent)
		self.item = item
		form.groups[item] = [self, None]
		self.update()

	def update(self):
		if self.item.info.title > '':
			self.setText(0, self.item.info.title)
		else:
			self.setText(0, '')

	def childCount(self):
		if QTreeWidgetItem.childCount(self) == 1 and isinstance(self.child(0), noChild):
			return 0
		else:
			return QTreeWidgetItem.childCount(self)

class treeItemSpacer(QTreeWidgetItem):
	def __init__(self, item, parent=None):
		super(treeItemSpacer, self).__init__(parent)

		self.item = item
		font = QFont()
		font.setItalic(True)
		self.setText(0, '<spacer>')
		self.setFont(0, font)
		self.setForeground(0, QColor(128, 128, 128))
		self.setFlags(self.flags() & ~(Qt.ItemIsDropEnabled))

class gridItemSpacer(QListWidgetItem):
	def __init__(self, item, parent=None):
		super(gridItemSpacer, self).__init__(parent)

		self.item = item
		pix = QImage(1, 1, QImage.Format_Mono)
		pix.fill(Qt.transparent)
		self.setIcon(QIcon(QPixmap.fromImage(pix)))
		self.setSizeHint(QSize(17, 17))
		self.setFlags(Qt.NoItemFlags)

class treeItemBreak(QTreeWidgetItem):
	def __init__(self, item, parent=None):
		super(treeItemBreak, self).__init__(parent)

		self.item = item
		font = QFont()
		font.setItalic(True)
		self.setText(0, '<break>')
		self.setFont(0, font)
		self.setForeground(0, QColor(128, 128, 128))
		self.setFlags(self.flags() & ~(Qt.ItemIsDropEnabled))

class gridItemBreak(QListWidgetItem):
	def __init__(self, item, parent=None):
		super(gridItemBreak, self).__init__(parent)

		self.item = item
		breaks.append(self)
		pix = QImage(1, 1, QImage.Format_Mono)
		pix.fill(Qt.transparent)
		self.setIcon(QIcon(QPixmap.fromImage(pix)))
		self.setSizeHint(QSize(0, 17))
		self.setFlags(Qt.NoItemFlags)

class gridItemGroup(gridItemBreak):
	def __init__(self, item, parent=None):
		super(gridItemGroup, self).__init__(item, parent)

class noChild(QTreeWidgetItem):
	def __init__(self, parent=None):
		super(noChild, self).__init__(parent)

		font = QFont()
		font.setItalic(True)
		self.setText(0, _('empty'))
		self.setFont(0, font)
		self.setForeground(0, QColor(128, 128, 128))
		self.setFlags(self.flags() & ~(Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled))

class matListWidget(QListWidget):
	def __init__(self, parent=None):
		super(matListWidget, self).__init__(parent)
		self.setSortingEnabled(True)
		self.setDragEnabled(True)

	def startDrag(self, supportedActions):
		indexes = self.selectedIndexes()
		data = self.model().mimeData(indexes)
		pixmap = QPixmap()
		rect = self.rectForIndex(indexes[0])
		rect.adjust(0, -self.verticalOffset(), 0, -self.verticalOffset())
		pixmap = self.grab(rect)
		drag = QDrag(self)
		drag.setPixmap(pixmap)
		data.setText(self.currentItem().id)
		drag.setMimeData(data)
		drag.setHotSpot(QPoint(pixmap.width() / 2, pixmap.height() / 2))
		drag.start(Qt.CopyAction)

class sbTreeWidget(QTreeWidget):
	def __init__(self, parent=None):
		super(sbTreeWidget, self).__init__(parent)
		self.setHeaderHidden(True)
		self.setDragEnabled(True)
		self.setDropIndicatorShown(True)
		self.setAcceptDrops(True)
		self.item = False
		self.itemParent = False

	def dropEvent(self, event):
		if event.source() == self:
			event.setDropAction(Qt.MoveAction)
			QTreeWidget.dropEvent(self, event)
			# Add or remove <empty>
			if self.itemParent and self.itemParent.childCount() == 0:
				self.itemParent.addChild(noChild())
			if isinstance(self.item.parent(), treeItemGroup):
				if isinstance(self.item.parent().child(0), noChild):
					self.item.parent().removeChild(self.item.parent().child(0))
				if isinstance(self.item.parent().child(self.item.parent().childCount() - 1), noChild):
					self.item.parent().removeChild(self.item.parent().child(self.item.parent().childCount() - 1))
			# Update the Python object
			if self.itemParent:
				swParent = self.itemParent.item
			else:
				swParent = form.sb.book
			sw = swParent.items.pop(swParent.items.index(self.item.item))
			if self.item.parent():
				self.item.parent().item.items.insert(self.item.parent().indexOfChild(self.item), sw)
			else:
				form.sb.book.items.insert(form.treeWidget.indexOfTopLevelItem(self.item), sw)
			# Update the grid
			gridItems = []
			self.gridItems(self.item, gridItems)
			for gridItem in gridItems:
				form.gridWidget.takeItem(form.gridWidget.indexFromItem(gridItem).row())
			self.setCurrentItem(self.item)
			itemAbove = self.swItemAbove(self.item)
			if itemAbove:
				index = form.gridWidget.indexFromItem(form.items[itemAbove]).row() + 1
			else:
				index = 0
			gridItems.reverse()
			for gridItem in gridItems:
				form.gridWidget.insertItem(index, gridItem)
		elif event.source() == form.matList:
			QTreeWidget.dropEvent(self, event)
			# Update the Python object + replace the generic QTreeWidgetItem with treeItemSwatch
			parent, index = self.dropped
			id = event.mimeData().text()
			sw = Swatch(id)
			newTreeItem = treeItemSwatch(sw)
			if parent:
				parent.item.items.insert(index, sw)
				form.treeWidget.expandItem(parent) # this is needed because taking an item from a collapsed group makes the child indicator disappear  
				parent.takeChild(index)
				parent.insertChild(index, newTreeItem)
			else:
				form.sb.book.items.insert(index, sw)
				self.takeTopLevelItem(index)
				self.insertTopLevelItem(index, newTreeItem)
			form.materials[id][1].append(newTreeItem)
			# Update the grid
			itemAbove = self.swItemAbove(newTreeItem)
			if itemAbove:
				index = form.gridWidget.indexFromItem(form.items[itemAbove]).row() + 1
			else:
				index = 0
			newGridItem = gridItemSwatch(sw)
			form.gridWidget.insertItem(index, newGridItem)
			form.materials[id][2].append(newGridItem)
			form.items[newTreeItem] = newGridItem
			self.setCurrentItem(newTreeItem)
			form.updSwatchCount()
		form.gridWidget.update()
		form.sw_display_tree()

	def swItemAbove(self, item):
		nitem = self.itemAbove(item)
		if isinstance(nitem, treeItemGroup):
			if nitem == item.parent() or not self.lastChild(nitem):
				nitem = self.swItemAbove(nitem)
			else:
				nitem = self.lastChild(nitem)
		elif isinstance(nitem, noChild):
			nitem = self.swItemAbove(nitem.parent())
		return nitem

	def lastChild(self, group):
		if group.childCount > 0:
			item = group.child(group.childCount() - 1)
			if isinstance(item, treeItemGroup):
				item = self.lastChild(item)
			return item

	def gridItems(self, item, gridItems):
		if isinstance(item, treeItemGroup):
			gridItems.append(form.groups[item.item][1][0])
			for i in range(item.childCount()):
				self.gridItems(item.child(i), gridItems)
			gridItems.append(form.groups[item.item][1][1])
		else:
			gridItems.append(form.items[item])

	def mousePressEvent(self, event):
		QTreeWidget.mousePressEvent(self, event)
		self.item = self.itemAt(event.pos())
		if self.item:
			self.itemParent = self.item.parent()

	def dragMoveEvent(self, event):
		if event.source() == self:
			event.setDropAction(Qt.MoveAction)
			QTreeWidget.dragMoveEvent(self, event)
		elif event.source() == form.matList:
			event.setDropAction(Qt.LinkAction)
			QTreeWidget.dragMoveEvent(self, event)
		else:
			event.ignore()

	def dropMimeData(self, parent, index, data, action):
		self.dropped = (parent, index)
		idx = QModelIndex()
		if parent: idx = self.indexFromItem(parent)
		return QAbstractItemModel.dropMimeData(self.model(), data, action , index, 0, idx)

class sbGridWidget(QListWidget):
	def __init__(self, parent=None):
		super(sbGridWidget, self).__init__(parent)
		self.setViewMode(QListView.IconMode)
		self.setMovement(QListView.Static)
		self.setResizeMode(QListView.Adjust)
		self.zHeight = self.zWidth = 2 * self.frameWidth()

	def update(self):
		if settings.contains('gridHoriz') and bool(settings.value('gridHoriz')):
			if form.sb.book.display['columns']:
				self.setFixedHeight(form.sb.book.display['columns'] * 17 + self.zHeight)
			else:
				self.setMinimumHeight(0)
				self.setMaximumHeight(0xFFFFFF)
			if form.sb.book.display['rows']:
				self.setFixedWidth(form.sb.book.display['rows'] * 17 + self.zWidth)
			else:
				self.setMinimumWidth(0)
				self.setMaximumWidth(0xFFFFFF)
			self.setFlow(QListView.TopToBottom)
			self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
			self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
			self.zWidth = 2 * self.frameWidth()
			self.zHeight = 2 * self.frameWidth() + self.horizontalScrollBar().size().height() + 1
			avail_height = self.size().height() - self.zHeight
			breaks2 = {}
			for item in breaks:
				breaks2[self.row(item)] = item
			for key in sorted(breaks2):
				if isinstance(self.item(key), gridItemGroup) and (isinstance(self.item(key - 1), gridItemBreak) or isinstance(self.item(key - 1), gridItemGroup) or key == 0):
					height = 0
				elif isinstance(self.item(key - 1), gridItemBreak) or key == 0:
					height = avail_height
				else:
					height = (int((avail_height - self.visualItemRect(self.item(key - 1)).top()) / 17) - 1) * 17
				breaks2[key].setSizeHint(QSize(17, height))
				self.doItemsLayout()
		else:
			if form.sb.book.display['columns']:
				self.setFixedWidth(form.sb.book.display['columns'] * 17 + self.zWidth)
			else:
				self.setMinimumWidth(0)
				self.setMaximumWidth(0xFFFFFF)
			if form.sb.book.display['rows']:
				self.setFixedHeight(form.sb.book.display['rows'] * 17 + self.zHeight)
			else:
				self.setMinimumHeight(0)
				self.setMaximumHeight(0xFFFFFF)
			self.setFlow(QListView.LeftToRight)
			self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
			self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
			self.zWidth = 2 * self.frameWidth() + self.verticalScrollBar().size().width() + 1
			self.zHeight = 2 * self.frameWidth()
			avail_width = self.size().width() - self.zWidth
			breaks2 = {}
			for item in breaks:
				breaks2[self.row(item)] = item
			for key in sorted(breaks2):
				if isinstance(self.item(key), gridItemGroup) and (isinstance(self.item(key - 1), gridItemBreak) or isinstance(self.item(key - 1), gridItemGroup) or key == 0):
					width = 0
				elif isinstance(self.item(key - 1), gridItemBreak) or key == 0:
					width = avail_width
				else:
					if self.isLeftToRight():
						width = (int((avail_width - self.visualItemRect(self.item(key - 1)).left()) / 17) - 1) * 17
					else:
						width = (int(self.visualItemRect(self.item(key - 1)).right() / 17) - 1) * 17
				breaks2[key].setSizeHint(QSize(width, 17))
				self.doItemsLayout()

	def resizeEvent(self, event):
		QListWidget.resizeEvent(self, event)
		self.update()

class GroupWidget(QGroupBox):
	def __init__(self, item, parent):
		super(GroupWidget, self).__init__(parent)

		self.setTitle(_("Group"))
		self.infoWidget = InfoWidget(item, self)
		infoScrollArea = QScrollArea()
		infoScrollArea.setWidget(self.infoWidget)
		infoScrollArea.setWidgetResizable(True)
		infoScrollArea.setFrameShape(QFrame.NoFrame)
		infoLayout = QVBoxLayout()
		infoLayout.addWidget(infoScrollArea)
		self.setLayout(infoLayout)

class MaterialWidget(QGroupBox):
	def __init__(self, id, parent):
		super(MaterialWidget, self).__init__(parent)

		self.item = form.sb.materials[id]

		self.infoWidget = InfoWidget(self.item, self)
		infoScrollArea = QScrollArea()
		infoScrollArea.setWidget(self.infoWidget)
		infoScrollArea.setWidgetResizable(True)
		palette = infoScrollArea.viewport().palette()
		palette.setColor(QPalette.Window, Qt.transparent)
		infoScrollArea.viewport().setPalette(palette)
		infoScrollArea.setFrameShape(QFrame.NoFrame)

		self.setTitle(_(self.item.__class__.__name__))
		self.swatch = eval(self.item.__class__.__name__ + 'Widget(id,self)')

		self.swExtra = QTableWidget()
		self.swExtra.setColumnCount(2)
		self.swExtra.horizontalHeader().setStretchLastSection(True)
		self.swExtra.verticalHeader().hide()
		self.swExtra.setHorizontalHeaderLabels([_("Key"), _("Value")])
		self.swExtra.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.butExtra = MenuButton(self)
		self.menuExtra = QMenu()
		self.menuExtra.addAction(_('Add'), self.addExtra)
		self.extraRemoveAction = self.menuExtra.addAction(_('Remove'), self.remExtra)
		self.butExtra.setMenu(self.menuExtra)
		self.extraRemoveAction.setEnabled(False)

		groupBoxExtra = QGroupBox(_("Extra info"))
		boxExtra = QHBoxLayout()
		boxExtra.addWidget(self.swExtra)
		boxExtra.addWidget(self.butExtra, 0, Qt.AlignTop)
		groupBoxExtra.setLayout(boxExtra)

		layout = QVBoxLayout()
		layout.addWidget(infoScrollArea)
		layout.addWidget(self.swatch)
		layout.addWidget(groupBoxExtra)
		self.setLayout(layout)

		self.tExtra = []
		row = 0
		for extra in self.item.extra:
			self.swExtra.insertRow(row)
			key = QTableWidgetItem(extra)
			if self.item.extra[extra]:
				val = QTableWidgetItem(self.item.extra[extra])
			else:
				val = QTableWidgetItem()
			self.swExtra.setItem(row, 0, key)
			self.swExtra.setItem(row, 1, val)
			row += 1
			self.tExtra.append([extra, self.item.extra[extra]])

		self.swExtra.cellChanged[int,int].connect(self.editExtra)
		self.swExtra.cellClicked[int,int].connect(self.extra_editable)

	def extra_editable(self):
		self.extraRemoveAction.setEnabled(True)

	def addExtra(self):
		self.swExtra.insertRow(self.swExtra.rowCount())
		if not hasattr(self, "tExtra"):
			self.tExtra = []
		self.tExtra.append([None, None])

	def remExtra(self):
		if self.swExtra.item(self.swExtra.currentRow(), 0):
			extra = self.swExtra.item(self.swExtra.currentRow(), 0).text()
			del self.item.extra[extra]
		self.swExtra.removeRow(self.swExtra.currentRow())
		self.extraRemoveAction.setEnabled(False)

	def editExtra(self):
		row, col = self.swExtra.currentRow(), self.swExtra.currentColumn()
		if col == 0:
			if self.tExtra[row][0] in self.item.extra:
				del self.item.extra[self.tExtra[row][0]]
			self.tExtra[row][0] = self.swExtra.item(row, col).text()
		else:
			self.tExtra[row][0] = self.swExtra.item(row, col).text()
			self.tExtra[row][col] = self.swExtra.item(row, col).text()
		if self.swExtra.item(row, 0):
			if self.swExtra.item(row, 1):
				self.item.extra[self.swExtra.item(row, 0).text()] = self.swExtra.item(row, 1).text()
			else:
				self.item.extra[self.swExtra.item(row, 0).text()] = None

class ColorWidget(QWidget):
	def __init__(self, id, parent):
		super(ColorWidget, self).__init__(parent)

		self.item = form.sb.materials[id]

		self.sample = SwatchPreview(self.item, self)
		self.sample.setMinimumHeight(30)
		self.usageSpot = QCheckBox(_("Spot"))
		self.valuesWidget = QTabWidget()
		self.butVal = MenuButton(self.valuesWidget)
		cornLay = QVBoxLayout()
		cornLay.setContentsMargins(20, 0, 0, 20)
		cornLay.addWidget(self.butVal)
		cornWid = QWidget()
		cornWid.setLayout(cornLay)
		cornWid.setMinimumSize(12, 12)
		self.menuVal = QMenu()
		self.menuValModl = self.menuVal.addMenu(_('Add'))
		for model in models:
			self.menuValModl.addAction(model, self.addVal)
		self.menuValModlN = self.menuValModl.addMenu('nCLR')
		for n in range(15):
			self.menuValModlN.addAction(("%X" % (n + 1)) + 'CLR', self.addVal)
		self.delValAction = self.menuVal.addAction(_('Remove'), self.delVal)
		self.delValAction.setEnabled(False)
		self.butVal.setMenu(self.menuVal)
		self.valuesWidget.setCornerWidget(cornWid)
		self.valuesWidget.setMovable(True)

		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.sample)
		layout.addWidget(self.usageSpot)
		layout.addWidget(self.valuesWidget)
		self.setLayout(layout)

		if 'spot' in self.item.usage:
			self.usageSpot.setChecked(True)
		self.val = {}
		if len(self.item.values) > 0:
			self.delValAction.setEnabled(True)
			self.sample.update()
			for space in self.item.values:
				self.add_val_tab(space, self.item.values[space])
		self.def_current_sp()

		# Actions
		self.usageSpot.stateChanged[int].connect(self.edit)
		self.valuesWidget.currentChanged[int].connect(self.def_current_sp)
		self.valuesWidget.tabBar().tabMoved[int,int].connect(self.tab_moved)

	def tab_moved(self, tfrom, tto):
		combo = self.valuesWidget.widget(tfrom).findChild(QComboBox)
		if combo and combo.currentIndex() > 0:
			space = combo.itemData(combo.currentIndex())
		else:
			space = False
		key = (self.valuesWidget.tabText(tfrom), space)
		val = self.item.values.pop(key)
		self.item.values.insert(tfrom, key, val)
		icon = form.drawIcon(self.item.info.identifier)
		form.addIcon(self.item.info.identifier, icon[0], icon[1])
		self.sample.update()

	def add_val_tab(self, space, values):
		profile = space[1]
		model = space[0]
		valWidget = QWidget()
		grid = QGridLayout()
		grid.setContentsMargins(0, 0, 0, 0)
		count = 0
		if model in models:
			for elem in models[model]:
				val = QLineEdit()
				self.val[val] = (space, count)
				val.textEdited[str].connect(self.valedit)
				grid.addWidget(QLabel(elem[0] + ":"), count, 0)
				if elem[1] == 0:
					grid.addWidget(val, count, 1)
					val.setText(str(round(values[count], 2)))
				elif elem[1] == 1:
					grid.addWidget(val, count, 1)
					grid.addWidget(QLabel("%"), count, 2)
					val.setText(str(round(values[count] * 100, 2)))
				if elem[1] == 2:
					grid.addWidget(val, count, 1)
					grid.addWidget(QLabel(u"°"), count, 2)
					val.setText(str(round(values[count] * 360, 2)))
				count += 1
		else:
			self.val[space] = {}
			for ink in values:
				val = QLineEdit()
				self.val[val] = (space, count)
				grid.addWidget(val, count, 1)
				grid.addWidget(QLabel("%"), count, 2)
				val.setText(str(round(values[count] * 100, 2)))
				count += 1

		valWidget.setLayout(grid)
		valScrollArea = QScrollArea()
		valScrollArea.setWidget(valWidget)
		valScrollArea.setWidgetResizable(True)
		palette = valScrollArea.viewport().palette()
		palette.setColor(QPalette.Window, Qt.transparent)
		valScrollArea.viewport().setPalette(palette)
		valScrollArea.setFrameShape(QFrame.NoFrame)

		spaceWidget = QWidget()
		spaceLayout = QVBoxLayout()
		spaceLayout.addWidget(valScrollArea)

		if model not in ('Lab', 'LCH', 'XYZ', 'sRGB'):
			spaceLayout.addWidget(QLabel(_("Profile")))
			if model in ('HSL', 'HSV', 'YIQ', 'CMY'):
				modellist = 'RGB'
			else:
				modellist = model
			profCombo = QComboBox()
			profCombo.addItem('')
			for prof in sorted(self.getProfList(modellist), cmp=lambda x, y: cmp(x[0].lower(), y[0].lower())):
				profCombo.addItem(prof[0], prof[1])
			if profile in form.sb.profiles:
				profCombo.setCurrentIndex(profCombo.findData(profile))
			profCombo.currentIndexChanged[int].connect(self.change_profile)
			spaceLayout.addWidget(profCombo)
		spaceWidget.setLayout(spaceLayout)

		self.valuesWidget.addTab(spaceWidget, model)
		icon = form.drawIcon(self.item.info.identifier)
		form.addIcon(self.item.info.identifier, icon[0], icon[1])
		self.sample.update()

	def edit(self):
		if self.sender() == self.usageSpot:
			if self.usageSpot.isChecked():
				self.item.usage.add('spot')
			else:
				self.item.usage.remove('spot')
			icon = form.drawIcon(self.item.info.identifier)
			form.addIcon(self.item.info.identifier, icon[0], icon[1])

	def valedit(self):
		sender = self.val[self.sender()]
		model = sender[0][0]
		if model in models:
			if models[model][sender[1]][1] == 0:
				self.item.values[sender[0]][sender[1]] = eval(self.sender().text())
			elif models[model][sender[1]][1] == 1:
				self.item.values[sender[0]][sender[1]] = eval(self.sender().text()) / 100
			elif models[model][sender[1]][1] == 2:
				self.item.values[sender[0]][sender[1]] = eval(self.sender().text()) / 360
		else:
			self.item.values[sender[0]][sender[1]] = eval(self.sender().text())
		icon = form.drawIcon(self.item.info.identifier)
		form.addIcon(self.item.info.identifier, icon[0], icon[1])
		self.sample.update()

	def def_current_sp(self):
		global current_sp
		if self.valuesWidget.count() > 0:
			widget = self.valuesWidget.currentWidget()
			model = self.valuesWidget.tabText(self.valuesWidget.currentIndex())
			combo = widget.findChild(QComboBox)
			if combo and combo.currentIndex() > 0:
				current_sp = (model, combo.itemData(combo.currentIndex()))
			else:
				current_sp = (model, False)
			if model in models:
				widget.findChild(QScrollArea).setFixedHeight(widget.findChild(QScrollArea).sizeHint().height())
			else:
				tmp_widget = QWidget()
				tmp_layout = QVBoxLayout()
				tmp_layout.addWidget(QLineEdit())
				tmp_layout.addWidget(QLineEdit())
				tmp_layout.addWidget(QLineEdit())
				tmp_widget.setLayout(tmp_layout)
				widget.findChild(QScrollArea).setFixedHeight(tmp_widget.sizeHint().height())
		else:
			current_sp = False

	def change_profile(self):
		global current_sp
		value = self.item.values[current_sp]
		del self.item.values[current_sp]
		self.def_current_sp()
		self.item.values[current_sp] = value
		fields = self.valuesWidget.currentWidget().findChildren(QLineEdit)
		for field in fields:
			self.val[field] = (current_sp, self.val[field][1])
		icon = form.drawIcon(self.item.info.identifier)
		form.addIcon(self.item.info.identifier, icon[0], icon[1])
		self.sample.update()

	def delVal(self):
		global current_sp
		del self.item.values[current_sp]
		self.valuesWidget.removeTab(self.valuesWidget.currentIndex())
		icon = form.drawIcon(self.item.info.identifier)
		form.addIcon(self.item.info.identifier, icon[0], icon[1])
		self.sample.update()

	def addVal(self):
		model = self.sender().text()
		if not hasattr(self, 'val'):
			self.val = {}
		self.item.values[(model, False)] = []
		if model in models:
			for elem in models[model]:
				self.item.values[(model, False)].append(0)
		elif len(model) == 4 and model[1:] == 'CLR':
			for ink in range(int(model[0], 16)):
				self.item.values[(model, False)].append(0)
		self.add_val_tab((model, False), self.item.values[(model, False)])
		self.valuesWidget.setCurrentIndex(self.valuesWidget.count() - 1)
		self.def_current_sp()
		self.delValAction.setEnabled(True)
		icon = form.drawIcon(self.item.info.identifier)
		form.addIcon(self.item.info.identifier, icon[0], icon[1])
		self.sample.update()

	def getProfList(self, model):
		profList = []
		if model in form.profiles:
			for prof in form.profiles[model]:
				profList.append((form.sb.profiles[prof].info['desc'][0], prof))
		return profList

class TintWidget(QWidget):
	def __init__(self, id, parent):
		super(TintWidget, self).__init__(parent)

		self.item = form.sb.materials[id]

		self.sample = SwatchPreview(self.item, self)

		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.sample)
		layout.addWidget(QLabel(self.item.color.info.identifier))
		layout.addWidget(QLabel(str(self.item.amount * 100) + '%'))
		self.setLayout(layout)
		
		self.sample.update()

class ToneWidget(QWidget):
	def __init__(self, id, parent):
		super(ToneWidget, self).__init__(parent)

		self.item = form.sb.materials[id]

		self.sample = SwatchPreview(self.item, self)

		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.sample)
		layout.addWidget(QLabel(self.item.color.info.identifier))
		layout.addWidget(QLabel(str(self.item.amount * 100) + '%'))
		self.setLayout(layout)
		
		self.sample.update()

class ShadeWidget(QWidget):
	def __init__(self, id, parent):
		super(ShadeWidget, self).__init__(parent)

		self.item = form.sb.materials[id]

		self.sample = SwatchPreview(self.item, self)

		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.sample)
		layout.addWidget(QLabel(self.item.color.info.identifier))
		layout.addWidget(QLabel(str(self.item.amount * 100) + '%'))
		self.setLayout(layout)
		
		self.sample.update()

class PatternWidget(QWidget):
	def __init__(self, id, parent):
		super(PatternWidget, self).__init__(parent)

		self.item = form.sb.materials[id]

		self.sample = SwatchPreview(self.item, self)
		self.sample.setMinimumHeight(100)

		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.sample)
		self.setLayout(layout)
		
		self.sample.update()

class GradientWidget(QWidget):
	def __init__(self, id, parent):
		super(GradientWidget, self).__init__(parent)
		
		self.item = form.sb.materials[id]

		self.sample = SwatchPreview(self.item, self)
		
		self.colorSample = QLabel()
		self.colorSampleUpdate()

		self.currentStop = False
		self.currentOpacityStop = False

		self.colorSlider = MultiSlider(self)
		self.colorSlider.setMaximum(10000)
		self.colorSlider.flipHandles = True
		for stop in self.item.colorstops:
			self.colorSlider.addHandle(stop.position * 10000)
		
		m = self.colorSlider.margins()
		colorSampleLayout = QVBoxLayout()
		colorSampleLayout.setContentsMargins(m, 0, m, 0)
		colorSampleLayout.addWidget(self.colorSample)

		self.colorIcon = QLabel()
		self.colorIcon.setFixedWidth(50)
		self.colorIcon.setFixedHeight(50)
		self.colorStopFormula = QLineEdit()
		colorEditLayout = QVBoxLayout()
		colorEditLayout.addWidget(self.colorIcon)
		colorEditLayout.addWidget(self.colorStopFormula)

		colorLayout = QVBoxLayout()
		colorLayout.setContentsMargins(0, 0, 0, 0)
		colorLayout.addLayout(colorSampleLayout)
		colorLayout.addWidget(self.colorSlider)
		colorLayout.addLayout(colorEditLayout)
		
		colorGroup = QGroupBox(_("Color stops"))
		colorGroup.setLayout(colorLayout)

		self.opacitySample = QLabel()
		self.opacitySlider = MultiSlider(self)
		self.opacitySlider.setMaximum(10000)
		self.opacitySlider.flipHandles = True
		for opstop in self.item.opacitystops:
			self.opacitySlider.addHandle(opstop.position * 10000)
		self.opacitySampleUpdate()

		self.opacitySpin = QSpinBox()
		self.opacitySpin.setMaximum(100)
		opacitySampleLayout = QVBoxLayout()
		opacitySampleLayout.setContentsMargins(m, 0, m, 0)
		opacitySampleLayout.addWidget(self.opacitySample)

		opacitySpinLayout = QHBoxLayout()
		opacitySpinLayout.addWidget(QLabel(_("Opacity:")))
		opacitySpinLayout.addWidget(self.opacitySpin)
		opacitySpinLayout.addWidget(QLabel("%"))
		
		opacityLayout = QVBoxLayout()
		opacityLayout.setContentsMargins(0, 0, 0, 0)
		opacityLayout.addLayout(opacitySampleLayout)
		opacityLayout.addWidget(self.opacitySlider)
		opacityLayout.addLayout(opacitySpinLayout)

		opacityGroup = QGroupBox(_("Transparency stops"))
		opacityGroup.setLayout(opacityLayout)

		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.sample)
		layout.addWidget(colorGroup)
		layout.addWidget(opacityGroup)
		self.setLayout(layout)

		self.colorEditReset()
		self.opacityEditReset()

		self.colorSlider.sliderMoved[int].connect(self.colorMove)
		self.colorSlider.sliderAdded[int].connect(self.colorAddStop)
		self.colorSlider.sliderDeleted[int].connect(self.colorDelStop)
		self.colorSlider.sliderPressed.connect(self.colorActivate)
		self.colorSlider.currentHandleChanged[int].connect(self.colorActivate)

		self.opacitySlider.sliderMoved[int].connect(self.opacityMove)
		self.opacitySlider.sliderAdded[int].connect(self.opacityAddStop)
		self.opacitySlider.sliderDeleted[int].connect(self.opacityDelStop)
		self.opacitySlider.sliderPressed.connect(self.opacityActivate)
		self.opacitySlider.currentHandleChanged[int].connect(self.opacityActivate)
		self.opacitySpin.valueChanged[int].connect(self.opacityEdit)

	def colorActivate(self):
		self.currentStop = sorted(self.colorSlider.handles).index(self.colorSlider.handles[0])
		if self.item.colorstops[self.currentStop].color:
			id = self.item.colorstops[self.currentStop].color
			palette = QLabel().palette()
			material = form.sb.materials[id]
			prof_out = settings.value("mntrProfile") or False
			RGB8 = material.toRGB8(prof_out)
			if RGB8:
				r, g, b = RGB8
				palette.setBrush(self.backgroundRole(), QBrush(QColor(r, g, b)))
			self.colorIcon.setPalette(palette)
			self.colorIcon.setAutoFillBackground(True)
			if material.info.title > '':
				text = material.info.title
			else:
				text = material.info.identifier
			self.colorIcon.setToolTip(text)
			self.colorStopFormula.setEnabled(True)
		else:
			self.colorIcon.setText(_("empty"))

	def colorEditReset(self):
		self.colorIcon.clear()
		self.colorIcon.setToolTip("")
		self.colorIcon.setPalette(QLabel().palette())
		self.colorStopFormula.setEnabled(False)
		self.colorStopFormula.clear()

	def colorMove(self, val):
		self.item.colorstops[self.currentStop].position = val / 10000
		self.colorSampleUpdate()

	def colorAddStop(self, val):
		stop = ColorStop()
		stop.position = val / 10000
		self.item.colorstops.insert(sorted(self.colorSlider.handles).index(val), stop)
		self.colorSampleUpdate()
		self.colorActivate()

	def colorDelStop(self, index):
		self.item.colorstops.pop(index)
		self.colorSampleUpdate()
		self.colorEditReset()

	def colorSampleUpdate(self):
		gradient = QLinearGradient(0, 0, 1, 0)
		gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
		palette = QLabel().palette()
		stops = self.item.colorstops
		prof_out = settings.value("mntrProfile") or False
		if len(stops) > 0:
			for i, stop in enumerate(stops):
				if i > 0 and stop.position == stops[i - 1].position:
					location = stop.position + 0.0001
				else:
					location = stop.position
				try:
					c = form.sb.materials[stop.color].toRGB8(prof_out) or (218, 218, 218)
				except KeyError:
					c = (218, 218, 218)
				gradient.setColorAt(location, QColor(c[0], c[1], c[2]))
			palette.setBrush(self.backgroundRole(), QBrush(gradient))
		else:
			palette.setBrush(self.backgroundRole(), QBrush(QColor(0, 0, 0)))
		self.colorSample.setPalette(palette)
		self.colorSample.setAutoFillBackground(True)
		self.sample.update()

	def opacityActivate(self):
		self.currentOpacityStop = sorted(self.opacitySlider.handles).index(self.opacitySlider.handles[0])
		self.opacitySpin.setValue(self.item.opacitystops[self.currentOpacityStop].opacity * 100)
		self.opacitySpin.setEnabled(True)

	def opacityEditReset(self):
		self.opacitySpin.setEnabled(False)
		self.opacitySpin.clear()

	def opacityEdit(self, val):
		self.item.opacitystops[self.currentOpacityStop].opacity = val / 100
		self.opacitySampleUpdate()

	def opacityMove(self, val):
		self.item.opacitystops[self.currentOpacityStop].position = val / 10000
		self.opacitySampleUpdate()

	def opacityAddStop(self, val):
		stop = OpacityStop()
		stop.position = val / 10000
		stop.opacity = 1
		self.item.opacitystops.insert(sorted(self.opacitySlider.handles).index(val), stop)
		self.opacitySampleUpdate()
		self.opacityActivate()

	def opacityDelStop(self, index):
		self.item.opacitystops.pop(index)
		self.opacitySampleUpdate()
		self.opacityEditReset()

	def opacitySampleUpdate(self):
		gradient = QLinearGradient(0, 0, 1, 0)
		gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
		palette = QLabel().palette()
		stops = self.item.opacitystops
		if len(stops) > 0:
			for i, stop in enumerate(stops):
				if i > 0 and stop.position == stops[i - 1].position:
					location = stop.position + 0.0001
				else:
					location = stop.position
				o = int((1 - stop.opacity) * 255)
				gradient.setColorAt(location, QColor(o, o, o))
			palette.setBrush(self.backgroundRole(), QBrush(gradient))
		else:
			palette.setBrush(self.backgroundRole(), QBrush(QColor(0, 0, 0)))
		self.opacitySample.setPalette(palette)
		self.opacitySample.setAutoFillBackground(True)
		self.sample.update()

class SwatchPreview(QLabel):
	def __init__(self, material, parent):
		super(SwatchPreview, self).__init__(parent)
		self.material = material
		self.setToolTip(_("Click to see in full screen"))

		palette = QLabel().palette()
		bgpix = QPixmap(16, 16)
		bgpix.fill(QColor(204, 204, 204))
		bgpaint = QPainter()
		bgpaint.begin(bgpix)
		bgpaint.setPen(Qt.transparent)
		bgpaint.setBrush(QColor(128, 128, 128))
		bgpaint.drawRect(8, 0, 8, 8)
		bgpaint.drawRect(0, 8, 8, 8)
		bgpaint.end()
		palette.setBrush(QPalette.Window, QBrush(bgpix))
		self.setPalette(palette)
		self.setAutoFillBackground(True)

	def update(self):
		s = self.size()
		pix = QPixmap(s)
		pix.fill(Qt.transparent)
		paint = QPainter()
		paint.begin(pix)
		paint.setPen(Qt.transparent)
		prof_out = settings.value("mntrProfile") or False
		if self.material.__class__.__name__ in ('Color', 'Tint', 'Tone', 'Shade'):
			RGB8 = self.material.toRGB8(prof_out)
			if RGB8:
				r, g, b = RGB8
				paint.setBrush(QBrush(QColor(r, g, b)))
		elif isinstance(self.material, Pattern) and self.material.image():
			image = QPixmap.fromImage(ImageQt.ImageQt(self.material.imageRGB(prof_out)))
			paint.setBrush(QBrush(image))
		elif isinstance(self.material, Gradient):
			image = QPixmap.fromImage(ImageQt.ImageQt(self.material.imageRGB(s.width(), s.height(), prof_out)))
			paint.setBrush(QBrush(image))
		paint.drawRect(0, 0, s.width(), s.height())
		paint.end()
		
		self.setPixmap(pix)

	def resizeEvent(self, event):
		QLabel.resizeEvent(self, event)
		self.update()

	def mousePressEvent(self, event):
		if self.isFullScreen():
			self.setWindowFlags(Qt.Widget)
			self.showNormal()
			self.releaseKeyboard()
			self.releaseMouse()
		else:
			self.setToolTip('')
			self.setWindowFlags(Qt.Window)
			self.showFullScreen()
			self.grabKeyboard()
			self.grabMouse()

	def keyPressEvent(self, event):
		if event.key() == Qt.Key_Escape:
			self.setWindowFlags(Qt.Widget)
			self.showNormal()
			self.releaseKeyboard()
			self.releaseMouse()
		else:
			QWidget.keyPressEvent(self, event)

class MultiSlider(QSlider):
	currentHandleChanged = pyqtSignal(int)
	sliderAdded = pyqtSignal(int)
	sliderDeleted = pyqtSignal(int)
	sliderMoved = pyqtSignal(int)
	sliderPressed = pyqtSignal()
	sliderReleased = pyqtSignal()

	# freely inspired by QT's code ;-) 
	def __init__(self, parent):
		super(MultiSlider, self).__init__(Qt.Horizontal, parent)
		self.handles = []

		self.pressedControl = QStyle.SC_None
		self.hoverControl = QStyle.SC_None
		self.hoverRect = QRect()
		self.clickOffset = 0
		self.flipHandles = False
		self.pressed = False
		self.position = False
		self.minSliders = 1
		
	def setCurrentHandle(self, handle):
		if handle != 0:
			self.handles.insert(0, self.handles.pop(handle))
			self.position = self.handles[0]
			self.currentHandleChanged.emit(handle)

	def addHandle(self, pos):
		self.handles.insert(0, pos)
		self.position = self.handles[0]
		self.update()

	def delHandle(self, handle):
		self.handles.pop(handle)
		if self.handles > 0:
			self.position = self.handles[0]
		else:
			self.position = False
		self.update()

	def margins(self):
		opt = QStyleOptionSlider()
		self.initStyleOption(opt)
		grooveRect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
		handleRect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
		widgetRect = opt.rect
		if self.orientation() == Qt.Horizontal:
			return (widgetRect.width() - grooveRect.width() + handleRect.width()) / 2
		else:
			return (widgetRect.height() - grooveRect.height() + handleRect.height()) / 2

	def __setLayoutItemMargins(self, element, opt=False):
		myOpt = QStyleOption()
		if not opt:
			myOpt.initFrom(self)
			myOpt.rect.setRect(0, 0, 32768, 32768)
			opt = myOpt

		liRect = self.style().subElementRect(element, opt, self)
		if liRect.isValid():
			self.leftLayoutItemMargin = opt.rect.left() - liRect.left()
			self.topLayoutItemMargin = opt.rect.top() - liRect.top()
			self.rightLayoutItemMargin = liRect.right() - opt.rect.right()
			self.bottomLayoutItemMargin = liRect.bottom() - opt.rect.bottom()
		else:
			self.leftLayoutItemMargin = 0
			self.topLayoutItemMargin = 0
			self.rightLayoutItemMargin = 0
			self.bottomLayoutItemMargin = 0

	def __resetLayoutItemMargins(self):
		opt = QStyleOptionSlider()
		self.initStyleOption(opt)
		self.__setLayoutItemMargins(QStyle.SE_SliderLayoutItem, opt)

	def __pixelPosToRangeValue(self, pos):
		opt = QStyleOptionSlider()
		self.initStyleOption(opt)
		gr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
		sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)

		sliderLength = sr.width()
		sliderMin = gr.x()
		sliderMax = gr.right() - sliderLength + 1

		return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), pos - sliderMin,
												sliderMax - sliderMin, opt.upsideDown)

	def __pick(self, pt):
		return pt.x()

	def __updateHoverControl(self, pos):
		if len(self.handles) > 0:
			lastHoverRect = self.hoverRect
			lastHoverControl = self.hoverControl
			lastHandle = self.handles[0]
			doesHover = self.testAttribute(Qt.WA_Hover)
			newHoverControl = self.__newHoverControl(pos)
			if ((lastHoverControl != newHoverControl or lastHandle != self.handles[0]) and doesHover):
				self.update(lastHoverRect)
				self.update(self.hoverRect)
				return True
			return not doesHover

	def __newHoverControl(self, pos):
		opt = QStyleOptionSlider()
		self.initStyleOption(opt)
		opt.subControls = QStyle.SC_All
		isHandle = False
		for i, hpos in enumerate(self.handles):
			opt.sliderPosition = hpos
			handleRect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
			if handleRect.contains(pos):
				isHandle = True
				if not self.pressed:
					self.setCurrentHandle(i)
				break
		if isHandle:
			self.hoverRect = handleRect
			self.hoverControl = QStyle.SC_SliderHandle
		else:
			self.hoverRect = QRect()
			self.hoverControl = QStyle.SC_None

		return self.hoverControl

	def paintEvent(self, event):
		p = QPainter(self)
		opt = QStyleOptionSlider()
		self.initStyleOption(opt)
		opt.subControls = QStyle.SC_SliderGroove
		opt.sliderPosition = self.minimum()
		w = opt.rect.width()
		h = opt.rect.height()
		rect1 = QRect(0, 0, int(w / 2), h)
		rect2 = QRect(int(w / 2), 0, int(w / 2) + w % 2, h)
		opt.upsideDown = True
		p.setClipRect(rect1)
		self.style().drawComplexControl(QStyle.CC_Slider, opt, p, self)
		opt.upsideDown = False
		p.setClipRect(rect2)
		self.style().drawComplexControl(QStyle.CC_Slider, opt, p, self)
		p.setClipping(False)
		self.initStyleOption(opt)
		opt.subControls = QStyle.SC_SliderHandle
		if self.flipHandles:
			sliderRect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
			p.scale(1, -1)
			p.translate(0, -2 * sliderRect.top() - sliderRect.height())
		for i, pos in enumerate(reversed(self.handles)):
			opt.sliderPosition = pos
			if self.pressedControl:
				opt.activeSubControls = self.pressedControl
				opt.state |= QStyle.State_Sunken
			else:
				opt.activeSubControls = self.hoverControl
			opt.state |= QStyle.State_HasFocus
			opt.state ^= QStyle.State_HasFocus
			self.style().drawComplexControl(QStyle.CC_Slider, opt, p, self)

	def event(self, event):
		type = event.type()
		if type in (QEvent.HoverEnter, QEvent.HoverLeave, QEvent.HoverMove):
			self.__updateHoverControl(event.pos())
		elif type == QEvent.StyleChange or (hasattr(QEvent, 'MacSizeChange') and type == QEvent.MacSizeChange):
			self.__resetLayoutItemMargins()
		return QAbstractSlider.event(self, event)

	def mouseDoubleClickEvent(self, event):
		event.accept()
		opt = QStyleOptionSlider()
		self.initStyleOption(opt)
		sliderRect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
		center = sliderRect.center() - sliderRect.topLeft()
		pos = self.__pixelPosToRangeValue(self.__pick(event.pos() - center))
		self.addHandle(pos)
		self.sliderAdded.emit(pos)

	def value(self, handle=False):
		if handle:
			return self.handles[handle]
		else:
			return self.handles[0]

	def setValue(self, value, handle=0):
		self.handles[handle] = self.bound(value, handle)
		if handle == 0:
			self.position = value

	def orderedHandles(self):
		handles = []
		for value in sorted(self.handles):
			handles.append(self.handles.index(value))
		return handles

	def bound(self, value, handle=0):
		handles = self.orderedHandles()
		index = handles.index(handle)
		if len(self.handles) == 1:
			pass
		elif index == 0:
			if value >= self.handles[handles[1]]:
				value = self.handles[handles[1]] - 1
		elif index > 0 and index == len(self.handles) - 1:
			if value <= self.handles[handles[-2]]:
				value = self.handles[handles[-2]] + 1
		else:
			if value >= self.handles[handles[index + 1]]:
				value = self.handles[handles[index + 1]] - 1
			if value <= self.handles[handles[index - 1]]:
				value = self.handles[handles[index - 1]] + 1
		if value > self.maximum():
			value = self.maximum()
		if value < self.minimum():
			value = self.minimum()
		return value

	def mousePressEvent(self, ev):
		if self.maximum() == self.minimum() or (ev.buttons() ^ ev.button()):
			ev.ignore()
			return
		try:
			if QApplication.keypadNavigationEnabled():
				setEditFocus(True)
		except AttributeError:
			pass
		ev.accept()
		if (ev.button() and self.style().styleHint(QStyle.SH_Slider_PageSetButtons)) == ev.button():
			opt = QStyleOptionSlider()
			self.initStyleOption(opt)

			isHandle = False
			for i, hpos in enumerate(self.handles):
				opt.sliderPosition = hpos
				handleRect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
				if handleRect.contains(ev.pos()):
					isHandle = True
					self.setCurrentHandle(i)
					break
			if isHandle:
				self.pressedControl = QStyle.SC_SliderHandle
				opt = QStyleOptionSlider()
				self.initStyleOption(opt)
				opt.sliderPosition = opt.sliderValue = self.handles[0]
				sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
				self.clickOffset = self.__pick(ev.pos() - sr.topLeft())
				self.snapBackPosition = self.position
				self.update(sr)
				self.setSliderDown(True)
		else:
			ev.ignore()
			return

	def mouseReleaseEvent(self, ev):
		if self.pressedControl == QStyle.SC_None or ev.buttons():
			ev.ignore()
			return
		ev.accept()
		oldPressed = QStyle.SubControl(self.pressedControl)
		self.pressedControl = QStyle.SC_None
		opt = QStyleOptionSlider()
		self.initStyleOption(opt)
		if oldPressed == QStyle.SC_SliderHandle:
			limit = opt.rect.height()
			pos = ev.pos().y()
			if (pos < 0 or pos > limit) and len(self.handles) > self.minSliders:
				index = sorted(self.handles).index(self.handles[0])
				self.delHandle(0)
				self.sliderDeleted.emit(index)
			self.setSliderDown(False)
		opt.subControls = oldPressed
		self.update(self.style().subControlRect(QStyle.CC_Slider, opt, oldPressed, self))

	def mouseMoveEvent(self, ev):
		if self.pressedControl != QStyle.SC_SliderHandle:
			ev.ignore()
			return
		ev.accept()
		newPosition = self.__pixelPosToRangeValue(self.__pick(ev.pos()) - self.clickOffset)
		opt = QStyleOptionSlider()
		self.initStyleOption(opt)
		m = self.style().pixelMetric(QStyle.PM_MaximumDragDistance, opt, self)
		if m >= 0:
			r = self.rect()
			r.adjust(-m, -m, m, m)
			if not r.contains(ev.pos()):
				newPosition = self.snapBackPosition
		self.setSliderPosition(newPosition)

	def setSliderPosition(self, position):
		position = self.bound(position)
		if position == self.position:
			return
		self.position = position
		self.handles[0] = position
		self.update()
		if self.pressed:
			self.sliderMoved.emit(position)
		self.triggerAction(QSlider.SliderMove)

	def setSliderDown(self, down):
		doEmit = self.pressed != down
		self.pressed = down
		if doEmit:
			if down:
				self.sliderPressed.emit()
			else:
				self.sliderReleased.emit()

class fileOpenThread(QThread):
	fileFormatError = pyqtSignal()

	def __init__(self, fname, parent=None):
		super(fileOpenThread, self).__init__(parent)
		self.fname = fname

	def run(self):
		try:
			self.parent().sb = SwatchBook(self.fname)
			self.parent().filename = self.fname
			if self.parent().sb.codec in codecs.writes:
				self.parent().codec = self.parent().sb.codec
		except FileFormatError:
			self.fileFormatError.emit()

class webOpenThread(QThread):
	def __init__(self, svc, id, parent=None):
		super(webOpenThread, self).__init__(parent)
		self.svc = svc
		self.id = id

	def run(self):
		self.parent().filename = False
		self.parent().codec = 'sbz'
		self.parent().sb = SwatchBook(websvc=self.svc, webid=self.id)

class fillViewsThread(QThread):
	filled = pyqtSignal()

	def __init__(self, parent=None):
		super(fillViewsThread, self).__init__(parent)

	def run(self):
		form.matList.setSortingEnabled(False)
		for id in form.sb.materials:
			form.addMaterial(id)
			self.filled.emit()
		form.matList.sortItems()
		form.matList.setSortingEnabled(True)
		self.fillViews(self.parent().sb.book.items)

	def fillViews(self, items, group=False):
		for item in items:
			if group:
				parent = group
			else:
				parent = form.treeWidget
			if isinstance(item, Group):
				gridItemIn = gridItemGroup(item, form.gridWidget)
				treeItem = treeItemGroup(item, parent)
				if len(item.items) > 0:
					self.fillViews(item.items, treeItem)
				else:
					nochild = noChild()
					treeItem.addChild(nochild)
				form.items[treeItem] = None
				gridItemOut = gridItemGroup(item, form.gridWidget)
				form.groups[item][1] = (gridItemIn, gridItemOut)
			elif isinstance(item, Spacer):
				treeItem = treeItemSpacer(item, parent)
				gridItem = gridItemSpacer(item, form.gridWidget)
				form.items[treeItem] = gridItem
			elif isinstance(item, Break):
				treeItem = treeItemBreak(item, parent)
				gridItem = gridItemBreak(item, form.gridWidget)
				form.items[treeItem] = gridItem
			else:
				treeItem = treeItemSwatch(item, parent)
				gridItem = gridItemSwatch(item, self.parent().gridWidget)
				form.items[treeItem] = gridItem
			self.filled.emit()

class drawIconThread(QThread):
	icon = pyqtSignal(str,QImage,QImage)

	def __init__(self, id, parent=None):
		super(drawIconThread, self).__init__(parent)
		self.id = id

	def run(self):
		icon = self.parent().drawIcon(self.id)
		self.icon.emit(self.id, icon[0], icon[1])

class LoadingDlg(QDialog):
	def __init__(self, parent=None):
		super(LoadingDlg, self).__init__(parent)
		self.setModal(True)
		self.setWindowFlags(Qt.ToolTip)

		self.label = QLabel()
		self.progress = QProgressBar()
		self.progress.hide()

		layout = QVBoxLayout()
		layout.addWidget(self.label)
		layout.addWidget(self.progress)
		self.setLayout(layout)

class SettingsDlg(QDialog):
	def __init__(self, parent=None):
		super(SettingsDlg, self).__init__(parent)

		self.mntrProfile = False
		self.cmykProfile = False
		self.profiles = []
		self.listProfiles()

		buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

		self.mntrCombo = QComboBox()
		self.cmykCombo = QComboBox()
		self.mntrCombo.addItem(_('sRGB built-in'))
		self.cmykCombo.addItem('Fogra27L')
		self.mntrCombo.insertSeparator(self.mntrCombo.count())
		self.cmykCombo.insertSeparator(self.cmykCombo.count())
		for profile in sorted(self.profiles, key=cmp_to_key(lambda x, y: cmp(x[0].lower(), y[0].lower()))):
			if profile[2] == "mntr" and profile[3] == 'RGB ':
				self.mntrCombo.addItem(profile[0], profile[1])
			if profile[3] == 'CMYK':
				self.cmykCombo.addItem(profile[0], profile[1])
		self.mntrCombo.insertSeparator(self.mntrCombo.count())
		self.cmykCombo.insertSeparator(self.cmykCombo.count())
		if settings.contains("mntrProfile") and self.mntrCombo.findData(settings.value("mntrProfile")) < 0:
			prof = ICCprofile(settings.value("mntrProfile")).info
			self.mntrCombo.addItem(prof['desc'][prof['desc'].keys()[0]], settings.value("mntrProfile"))
		if settings.contains("cmykProfile") and self.cmykCombo.findData(settings.value("cmykProfile")) < 0:
			prof = ICCprofile(settings.value("cmykProfile")).info
			self.cmykCombo.addItem(prof['desc'][prof['desc'].keys()[0]], settings.value("cmykProfile"))
		self.mntrCombo.addItem(_("Other..."))
		self.cmykCombo.addItem(_("Other..."))

		profilesBox = QGroupBox(_("Color profiles"))
		profilesLayout = QVBoxLayout()
		profilesLayout.addWidget(QLabel(_("Display Profile")))
		profilesLayout.addWidget(self.mntrCombo)
		profilesLayout.addWidget(QLabel(_("Default CMYK Profile")))
		profilesLayout.addWidget(self.cmykCombo)
		profilesBox.setLayout(profilesLayout)

		self.RecFilesSpin = QSpinBox()
		self.RecFilesSpin.setRange(0, 12)

		gRecFiles = QGroupBox(_("Recent files"))
		RecFiles = QHBoxLayout()
		RecFiles.addWidget(QLabel(_("Number of files displayed:")))
		RecFiles.addWidget(self.RecFilesSpin)
		gRecFiles.setLayout(RecFiles)

		self.LangCombo = QComboBox()
		self.LangCombo.addItem(_('(default)'))
		for lang in sorted(availables_lang):
			self.LangCombo.addItem(availables_lang[lang], lang)

		gLang = QGroupBox(_("Application language"))
		Lang = QHBoxLayout()
		Lang.addWidget(self.LangCombo)
		gLang.setLayout(Lang)

		sett = QVBoxLayout()
		sett.addWidget(profilesBox)
		sett.addWidget(gRecFiles)
		sett.addWidget(gLang)
		sett.addWidget(buttonBox)
		self.setLayout(sett)

		if settings.contains("mntrProfile"):
			self.mntrProfile = settings.value("mntrProfile")
			self.mntrCombo.setCurrentIndex(self.mntrCombo.findData(self.mntrProfile))
		else:
			self.mntrCombo.setCurrentIndex(0)
		if settings.contains("CMYKProfile"):
			self.cmykProfile = settings.value("cmykProfile")
			self.cmykCombo.setCurrentIndex(self.cmykCombo.findData(self.cmykProfile))
		else:
			self.cmykCombo.setCurrentIndex(0)
		self.RecFilesSpin.setValue(int(settings.value("MaxRecentFiles")))
		self.lang = False
		if settings.contains("Language"):
			self.lang = settings.value("Language")
			self.LangCombo.setCurrentIndex(self.LangCombo.findData(self.lang))

		buttonBox.accepted.connect(self.accept)
		buttonBox.rejected.connect(self.reject)
		self.mntrCombo.currentIndexChanged[int].connect(self.setProfile)
		self.cmykCombo.currentIndexChanged[int].connect(self.setProfile)
		self.LangCombo.currentIndexChanged[int].connect(self.setLang)
		self.setWindowTitle(_("Settings"))

	def returnDisProf(self):
		if hasattr(self, 'mntrProfile'):
			return self.mntrProfile

	def returnCMYKProf(self):
		if hasattr(self, 'cmykProfile'):
			return self.cmykProfile

	def setRGBFile(self):
		fname = QFileDialog.getOpenFileName(self, _("Choose file"), QDir.homePath(), _("ICC profiles (*.icc *.icm);;" + _("All files (*)")))[0]
		if fname:
			profile = icc.ICCprofile(fname)
			if profile.info['class'] == "mntr" and profile.info['space'] == 'RGB ':
				self.mntrCombo.setCurrentIndex(0)
				self.mntrCombo.insertItem(self.mntrCombo.count() - 1, profile.info['desc'][profile.info['desc'].keys()[0]], fname)
				self.mntrCombo.setCurrentIndex(self.mntrCombo.findData(fname))
			else:
				QMessageBox.critical(self, _('Error'), _("This isn't a RGB monitor profile"))
				if self.mntrProfile:
					self.mntrCombo.setCurrentIndex(self.mntrCombo.findData(self.mntrProfile) or 0)
				else:
					self.mntrCombo.setCurrentIndex(0)
		else:
			if self.mntrProfile:
				self.mntrCombo.setCurrentIndex(self.mntrCombo.findData(self.mntrProfile) or 0)
			else:
				self.mntrCombo.setCurrentIndex(0)

	def setCMYKFile(self):
		fname = QFileDialog.getOpenFileName(self, _("Choose file"), QDir.homePath(), _("ICC profiles (*.icc *.icm);;" + _("All files (*)")))[0]
		if fname:
			profile = icc.ICCprofile(fname)
			if profile.info['space'] == 'CMYK':
				self.cmykCombo.setCurrentIndex(0)
				self.cmykCombo.insertItem(self.cmykCombo.count() - 1, profile.info['desc'][profile.info['desc'].keys()[0]], fname)
				self.cmykCombo.setCurrentIndex(self.cmykCombo.findData(fname))
			else:
				QMessageBox.critical(self, _('Error'), _("This isn't a CMYK profile"))
				if self.cmykProfile:
					self.cmykCombo.setCurrentIndex(self.cmykCombo.findData(self.cmykProfile) or 0)
				else:
					self.cmykCombo.setCurrentIndex(0)
		else:
			if self.cmykProfile:
				self.cmykCombo.setCurrentIndex(self.cmykCombo.findData(self.cmykProfile) or 0)
			else:
				self.cmykCombo.setCurrentIndex(0)

	def setLang(self, index):
		if index > 0:
			self.lang = self.sender().itemData(index)
		else:
			self.lang = False

	def setProfile(self, index):
		if self.sender() == self.mntrCombo:
			if index == self.mntrCombo.count() - 1:
				self.setRGBFile()
			elif index > 0:
				self.mntrProfile = self.sender().itemData(index)
			else:
				self.mntrProfile = False
		elif self.sender() == self.cmykCombo:
			if index == self.cmykCombo.count() - 1:
				self.setCMYKFile()
			elif index > 0:
				self.cmykProfile = self.sender().itemData(index)
			else:
				self.cmykProfile = False

	def listProfiles(self):
		def listprof(dir):
			for s in os.listdir(dir):
				file = os.path.join(dir, s)
				if os.path.isdir(file) and s not in ('.', '..'):
					listprof(file)
				else:
					if os.path.isfile(file) and os.path.splitext(os.path.basename(file))[1].lower()[1:] in ('icc', 'icm', '3cc') and not os.path.islink(file):
						try:
							prof = ICCprofile(file).info
							self.profiles.append((prof['desc'][prof['desc'].keys()[0]], file, prof['class'], prof['space']))
						except BadICCprofile:
							pass
		if os.name == 'posix':
			profdirs = [QDir.homePath() + "/.color/icc", "/usr/share/color/icc", "/usr/local/share/color/icc", "/var/lib/color/icc", QDir.homePath() + "/.local/share/icc"]
		elif os.name == 'nt':
			profdirs = ["C:\\Windows\\System\\Color", "C:\\Winnt\\system32\\spool\\drivers\\color", "C:\\Windows\\system32\\spool\\drivers\\color"]
		elif os.name == 'mac':
			profdirs = ["/Network/Library/ColorSync/Profiles", "/System/Library/Colorsync/Profiles", "/Library/ColorSync/Profiles", QDir.homePath() + "/Library/ColorSync/Profiles"]
		else:
			profdirs = []
		for profdir in profdirs:
			if os.path.exists(profdir):
				listprof(profdir)

if __name__ == "__main__":
	app = QApplication(sys.argv)
	app.setOrganizationName("Selapa")
	app.setOrganizationDomain("selapa.net")
	app.setApplicationName("SwatchBooker")
	settings = QSettings()

	translate_sb(app, settings, globals())

	if len(sys.argv) > 1:
		form = MainWindow(sys.argv[1])
	else:
		form = MainWindow()
	form.show()
	form.dispPane()

	app.exec_()
