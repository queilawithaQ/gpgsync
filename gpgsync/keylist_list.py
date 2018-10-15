# -*- coding: utf-8 -*-
"""
GPG Sync
Helps users have up-to-date public keys for everyone in their organization
https://github.com/firstlookmedia/gpgsync
Copyright (C) 2016 First Look Media

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import queue
from PyQt5 import QtCore, QtWidgets, QtGui

from .keylist import Keylist, RefresherMessageQueue
from .keylist_dialog import KeylistDialog


class KeylistList(QtWidgets.QWidget):
    refresh = QtCore.pyqtSignal()

    def __init__(self, common):
        super(KeylistList, self).__init__()
        self.c = common

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(10)
        self.setLayout(self.layout)

        self.update_ui()

    def update_ui(self):
        # Delete all widgets from the layout
        # https://stackoverflow.com/questions/4528347/clear-all-widgets-in-a-layout-in-pyqt
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().setParent(None)

        # Add new keylist widgets
        for e in self.c.settings.keylists:
            widget = KeylistWidget(self.c, e)
            widget.refresh.connect(self.refresh.emit)
            self.layout.addWidget(widget)

        self.adjustSize()


class KeylistWidget(QtWidgets.QWidget):
    refresh = QtCore.pyqtSignal()

    def __init__(self, common, keylist):
        super(KeylistWidget, self).__init__()
        self.c = common
        self.keylist = keylist

        self.c.log("KeylistWidget", "__init__")

        # Authority Key user ID
        uid = self.c.gpg.get_uid(self.keylist.fingerprint)
        uid_label = QtWidgets.QLabel(uid)
        uid_label.setMinimumSize(440, 30)
        uid_label.setMaximumSize(440, 30)
        uid_label.setStyleSheet(self.c.gui.css['KeylistWidget uid_label'])

        # Status
        if self.keylist.syncing:
            status_text = "Syncing now..."
            status_css = self.c.gui.css['KeylistWidget status_label']
        else:
            if self.keylist.error:
                status_text = 'Error syncing'
                status_css = self.c.gui.css['KeylistWidget status_label_error']
            else:
                if self.keylist.last_synced:
                    status = self.keylist.last_synced.strftime("%B %d, %I:%M %p")
                else:
                    status = "Never"
                status_text = "Synced {}".format(status)
                if self.keylist.warning:
                    status_css = self.c.gui.css['KeylistWidget status_label_warning']
                else:
                    status_css = self.c.gui.css['KeylistWidget status_label']
        self.status_label = QtWidgets.QLabel(status_text)
        self.status_label.setStyleSheet(status_css)
        self.status_label.setMinimumSize(440, 20)
        self.status_label.setMaximumSize(440, 20)

        # Sync progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimumSize(290, 20)
        self.progress_bar.setMaximumSize(290, 20)
        self.progress_bar.hide()

        # Buttons
        info_button = QtWidgets.QPushButton("Info")
        info_button.clicked.connect(self.details_clicked)
        info_button.setStyleSheet(self.c.gui.css['KeylistWidget button'])
        sync_button = QtWidgets.QPushButton("Sync Now")
        sync_button.clicked.connect(self.sync_clicked)
        sync_button.setStyleSheet(self.c.gui.css['KeylistWidget button'])
        edit_button = QtWidgets.QPushButton("Edit")
        edit_button.clicked.connect(self.edit_clicked)
        edit_button.setStyleSheet(self.c.gui.css['KeylistWidget button'])
        delete_button = QtWidgets.QPushButton("Delete")
        delete_button.clicked.connect(self.delete_clicked)
        delete_button.setStyleSheet(self.c.gui.css['KeylistWidget button'])
        #delete_button.setMinimumHeight(30)
        self.cancel_sync_button = QtWidgets.QPushButton("Cancel Sync")
        self.cancel_sync_button.clicked.connect(self.cancel_sync_clicked)
        self.cancel_sync_button.setStyleSheet(self.c.gui.css['KeylistWidget button'])

        if self.keylist.syncing:
            info_button.hide()
            sync_button.hide()
            edit_button.hide()
            delete_button.hide()
        else:
            self.cancel_sync_button.hide()

            if self.keylist.error or self.keylist.warning:
                info_button.show()
            else:
                info_button.hide()

        # Layout
        hlayout = QtWidgets.QHBoxLayout()
        hlayout.setSpacing(4)
        hlayout.addWidget(self.status_label)
        hlayout.addWidget(self.progress_bar)
        hlayout.addStretch()
        hlayout.addWidget(info_button)
        hlayout.addWidget(sync_button)
        hlayout.addWidget(edit_button)
        hlayout.addWidget(delete_button)
        hlayout.addWidget(self.cancel_sync_button)
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(uid_label)
        layout.addLayout(hlayout)
        self.setLayout(layout)

        # Size
        self.setMinimumSize(440, 70)
        self.setMaximumSize(440, 70)

        # Update timer
        self.update_ui_timer = QtCore.QTimer()
        self.update_ui_timer.timeout.connect(self.update_ui)
        self.update_ui_timer.start(100) # 0.1 seconds

    def details_clicked(self):
        self.c.log("KeylistWidget", "details_clicked")
        if self.keylist.error:
            self.c.gui.alert("Sync error:\n\n{}".format(self.keylist.error), icon=QtWidgets.QMessageBox.Critical)
        elif self.keylist.warning:
            self.c.gui.alert("Sync warning:\n\n{}".format(self.keylist.warning), icon=QtWidgets.QMessageBox.Warning)

    def sync_clicked(self):
        self.c.log("KeylistWidget", "sync_clicked")
        self.keylist.start_syncing(force=True)
        self.refresh.emit()

    def cancel_sync_clicked(self):
        self.c.log("KeylistWidget", "cancel_sync_clicked")
        self.cancel_sync_button.setText("Canceling...")
        self.cancel_sync_button.setEnabled(False)
        self.keylist.refresher.cancel_early()

    def edit_clicked(self):
        self.c.log("KeylistWidget", "edit_clicked")
        d = KeylistDialog(self.c, keylist=self.keylist)
        d.saved.connect(self.refresh.emit)
        d.exec_()

    def delete_clicked(self):
        self.c.log("KeylistWidget", "delete_clicked")
        uid = self.c.gpg.get_uid(self.keylist.fingerprint)
        alert_text = "Are you sure you want to delete this keylist?<br><br><b>{}</b>".format(uid)
        reply = self.c.gui.alert(alert_text, icon=QtWidgets.QMessageBox.Critical, question=True)
        if reply == 0:
            # Delete
            self.c.settings.keylists.remove(self.keylist)
            self.c.settings.save()
            self.refresh.emit()

    def update_ui(self):
        # Only need to update the UI if the keylist is syncing
        if self.keylist.syncing:
            # Process the last event in the LIFO queue, ignore the rest
            try:
                event = self.keylist.q.get(False)
                if event['status'] == RefresherMessageQueue.STATUS_IN_PROGRESS:
                    self.status_label.hide()
                    self.progress_bar.show()
                    self.progress_bar.setRange(0, event['total_keys'])
                    self.progress_bar.setValue(event['current_key'])

            except queue.Empty:
                pass
