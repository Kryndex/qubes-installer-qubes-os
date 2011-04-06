#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2011  Tomasz Sterna <tomek@xiaoka.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
import gtk
import os, string, sys, time
import threading, subprocess, grp

from firstboot.config import *
from firstboot.constants import *
from firstboot.functions import *
from firstboot.module import *

import gettext
_ = lambda x: gettext.ldgettext("firstboot", x)
N_ = lambda x: x

class moduleClass(Module):
    netvm_name = "netvm"
    fwvm_name  = "firewallvm"

    def __init__(self):
        Module.__init__(self)
        self.priority = 10000
        self.sidebarTitle = N_("Create Service VMs")
        self.title = N_("Create Service VMs")
        self.icon = "qubes.png"

    def apply(self, interface, testing=False):
        try:
            if self.progress is None:
                self.progress = gtk.ProgressBar()
                self.progress.set_pulse_step(0.06)
                self.vbox.pack_start(self.progress, True, False)
            self.progress.show()

            if testing:
                return RESULT_SUCCESS

            self.create_default_netvm()
            self.create_default_fwvm()
            self.set_networking_type(netvm=True)
            self.start_qubes_networking()
            self.configure_template()
            self.create_default_dvm()

            return RESULT_SUCCESS
        except Exception as e:
            md = gtk.MessageDialog(interface.win, gtk.DIALOG_DESTROY_WITH_PARENT,
                    gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                    self.stage + " failure!\n\n" + str(e))
            md.run()
            md.destroy()
            self.show_stage("Failure...")
            self.progress.hide()
            return RESULT_FAILURE

    def show_stage(self, stage):
        self.stage = stage
        self.progress.set_text(stage)

    def configure_template(self):
        self.show_stage(_("Configuring default Temaple"))
        self.run_in_thread(self.do_configure_template)

    def run_in_thread(self, method):
        thread = threading.Thread(target=method)
        thread.start()
        count = 0
        while thread.is_alive():
            self.progress.pulse()
            while gtk.events_pending():
                gtk.main_iteration(False)
            time.sleep(0.1)
        if self.process_error is not None:
            raise Exception(self.process_error)

    def create_default_netvm(self):
        self.show_stage(_("Creating default NetworkVM"))
        self.run_in_thread(self.do_create_netvm)

    def create_default_fwvm(self):
        self.show_stage(_("Creating default FirewallVM"))
        self.run_in_thread(self.do_create_fwvm)

    def create_default_dvm(self):
        self.show_stage(_("Creating default DisposableVM"))
        self.run_in_thread(self.do_create_dvm)

    def set_networking_type(self, netvm):
        if netvm:
            self.show_stage(_("Setting FirewallVM + NetworkVM networking"))
            self.run_in_thread(self.do_set_netvm_networking)
        else:
            self.show_stage(_("Setting Dom0 networking"))
            self.run_in_thread(self.do_set_dom0_networking)

    def start_qubes_networking (self):
        self.show_stage(_("Starting Qubes networking"))
        self.run_in_thread(self.do_start_networking)

    def run_command(self, command):
        try:
            os.setgid(self.qubes_gid)
            os.umask(0007)
            cmd = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = cmd.communicate()[0]
            if cmd.returncode == 0:
                self.process_error = None
            else:
                self.process_error = out
        except Exception as e:
            self.process_error = str(e)

    def do_create_netvm(self):
        self.run_command(['/usr/bin/qvm-create', '--net', '--label', 'red', self.netvm_name])

    def do_create_fwvm(self):
        self.run_command(['/usr/bin/qvm-create', '--proxy', '--label', 'red', self.fwvm_name])

    def do_create_dvm(self):
        self.run_command(['/usr/bin/qvm-create-default-dvm', '--default-template', '--default-script'])

    def do_set_netvm_networking(self):
        self.run_command(['/usr/bin/qvm-prefs', '--set', self.fwvm_name, 'netvm', self.netvm_name])
        self.run_command(['/usr/bin/qvm-set-default-netvm', self.fwvm_name])

    def do_set_dom0_networking(self):
        self.run_command(['/usr/bin/qvm-set-default-netvm', 'dom0'])

    def do_start_networking(self):
        subprocess.check_call(['/etc/init.d/qubes_netvm', 'start'])

    def do_configure_template(self):
        subprocess.check_call(['/bin/mkdir', '/mnt/template-root'])
        subprocess.check_call(['/bin/mount', '-oloop',
            '/var/lib/qubes/vm-templates/fedora-14-x64/root.img',
            '/mnt/template-root'])
        # Copy timezone setting from Dom0 to template
        subprocess.check_call(['cp', '/etc/localtime', '/mnt/template-root/etc'])
        subprocess.check_call(['/bin/umount', '/mnt/template-root'])

    def createScreen(self):
        self.vbox = gtk.VBox(spacing=5)

        label = gtk.Label(_("Almost there! We just need to create a few service VMs."
                            "This will take a few minutes...\n\n"))
        label.set_line_wrap(True)
        label.set_alignment(0.0, 0.5)
        label.set_size_request(500, -1)
        self.vbox.pack_start(label, False, True, padding=20)

        self.progress = None

    def initializeUI(self):
        self.qubes_gid = grp.getgrnam('qubes').gr_gid
        self.stage = "Initialization"
        self.process_error = None