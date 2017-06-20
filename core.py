#
# Copyright 2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

import os.path

from vdsm import constants
from vdsm import utils

import caps
import supervdsm

from ..utils import cleanup_guest_socket
from .. import vmxml


class SkipDevice(Exception):
    pass


class Base(vmxml.Device):
    __slots__ = ('deviceType', 'device', 'alias', 'specParams', 'deviceId',
                 'conf', 'log', '_deviceXML', 'type', 'custom')

    def __init__(self, conf, log, **kwargs):
        self.conf = conf
        self.log = log
        self.specParams = {}
        self.custom = kwargs.pop('custom', {})
        for attr, value in kwargs.iteritems():
            try:
                setattr(self, attr, value)
            except AttributeError:  # skip read-only properties
                self.log.debug('Ignoring param (%s, %s) in %s', attr, value,
                               self.__class__.__name__)
        self._deviceXML = None

    def __str__(self):
        attrs = [':'.join((a, str(getattr(self, a, None)))) for a in dir(self)
                 if not a.startswith('__')]
        return ' '.join(attrs)

    def is_attached_to(self, xml_string):
        raise NotImplementedError(
            "%s does not implement is_attached_to", self.__class__.__name__)


class Generic(Base):

    def getXML(self):
        """
        Create domxml for general device
        """
        return self.createXmlElem(self.type, self.device, ['address'])


class Balloon(Base):
    __slots__ = ('address',)

    def getXML(self):
        """
        Create domxml for a memory balloon device.

        <memballoon model='virtio'>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x04'
           function='0x0'/>
        </memballoon>
        """
        m = self.createXmlElem(self.device, None, ['address'])
        m.setAttrs(model=self.specParams['model'])
        return m


class Console(Base):
    __slots__ = ('_path',)

    CONSOLE_EXTENSION = '.sock'

    def __init__(self, *args, **kwargs):
        super(Console, self).__init__(*args, **kwargs)
        if not hasattr(self, 'specParams'):
            self.specParams = {}

        if utils.tobool(self.specParams.get('enableSocket', False)):
            self._path = os.path.join(
                constants.P_OVIRT_VMCONSOLES,
                self.conf['vmId'] + self.CONSOLE_EXTENSION
            )
        else:
            self._path = None

    def prepare(self):
        if self._path:
            supervdsm.getProxy().prepareVmChannel(
                self._path,
                constants.OVIRT_VMCONSOLE_GROUP)

    def cleanup(self):
        if self._path:
            cleanup_guest_socket(self._path)

    @property
    def isSerial(self):
        return self.specParams.get('consoleType', 'virtio') == 'serial'

    def getSerialDeviceXML(self):
        """
        Add a serial port for the console device if it exists and is a
        'serial' type device.

        <serial type='pty'>
            <target port='0'>
        </serial>

        or

        <serial type='unix'>
            <source mode='bind'
              path='/var/run/ovirt-vmconsole-console/${VMID}.sock'/>
            <target port='0'/>
        </serial>
        """
        if self._path:
            s = self.createXmlElem('serial', 'unix')
            s.appendChildWithArgs('source', mode='bind', path=self._path)
        else:
            s = self.createXmlElem('serial', 'pty')
        s.appendChildWithArgs('target', port='0')
        return s

    def getXML(self):
        """
        Create domxml for a console device.

        <console type='pty'>
          <target type='serial' port='0'/>
        </console>

        or:

        <console type='pty'>
          <target type='virtio' port='0'/>
        </console>

        or

        <console type='unix'>
          <source mode='bind' path='/path/to/${vmid}.sock'>
          <target type='virtio' port='0'/>
        </console>
        """
        if self._path:
            m = self.createXmlElem('console', 'unix')
            m.appendChildWithArgs('source', mode='bind', path=self._path)
        else:
            m = self.createXmlElem('console', 'pty')
        consoleType = self.specParams.get('consoleType', 'virtio')
        m.appendChildWithArgs('target', type=consoleType, port='0')
        return m


class Controller(Base):
    __slots__ = ('address', 'model', 'index', 'master')

    def getXML(self):
        """
        Create domxml for controller device
        """
        ctrl = self.createXmlElem('controller', self.device,
                                  ['index', 'model', 'master', 'address'])
        if self.device == 'virtio-serial':
            ctrl.setAttrs(index='0', ports='16')

        return ctrl


class Smartcard(Base):
    __slots__ = ('address',)

    def getXML(self):
        """
        Add smartcard section to domain xml

        <smartcard mode='passthrough' type='spicevmc'>
          <address ... />
        </smartcard>
        """
        card = self.createXmlElem(self.device, None, ['address'])
        sourceAttrs = {'mode': self.specParams['mode']}
        if sourceAttrs['mode'] != 'host':
            sourceAttrs['type'] = self.specParams['type']
        card.setAttrs(**sourceAttrs)
        return card


class Sound(Base):
    __slots__ = ('address')

    def getXML(self):
        """
        Create domxml for sound device
        """
        sound = self.createXmlElem('sound', None, ['address'])
        sound.setAttrs(model='ac97')
        return sound


class Redir(Base):
    __slots__ = ('address',)

    def getXML(self):
        """
        Create domxml for a redir device.
        <redirdev bus='usb' type='spicevmc'>
          <address type='usb' bus='0' port='1'/>
        </redirdev>
        """
        return self.createXmlElem('redirdev', self.device, ['bus', 'address'])


class Rng(Base):
    def getXML(self):
        """
        <rng model='virtio'>
            <rate period="2000" bytes="1234"/>
            <backend model='random'>/dev/random</backend>
        </rng>
        """
        rng = self.createXmlElem('rng', None, ['model'])

        # <rate... /> element
        if 'bytes' in self.specParams:
            rateAttrs = {'bytes': self.specParams['bytes']}
            if 'period' in self.specParams:
                rateAttrs['period'] = self.specParams['period']

            rng.appendChildWithArgs('rate', None, **rateAttrs)

        # <backend... /> element
        rng.appendChildWithArgs('backend',
                                caps.RNG_SOURCES[self.specParams['source']],
                                model='random')

        return rng


class Tpm(Base):
    __slots__ = ()

    def getXML(self):
        """
        Add tpm section to domain xml

        <tpm model='tpm-tis'>
            <backend type='passthrough'>
                <device path='/dev/tpm0'>
            </backend>
        </tpm>
        """
        tpm = self.createXmlElem(self.device, None)
        tpm.setAttrs(model=self.specParams['model'])
        backend = tpm.appendChildWithArgs('backend',
                                          type=self.specParams['mode'])
        backend.appendChildWithArgs('device',
                                    path=self.specParams['path'])
        return tpm


class Video(Base):
    def getXML(self):
        """
        Create domxml for video device
        """
        video = self.createXmlElem('video', None, ['address'])
        sourceAttrs = {'vram': self.specParams.get('vram', '32768'),
                       'heads': self.specParams.get('heads', '1')}
        for attr in ('ram', 'vgamem',):
            if attr in self.specParams:
                sourceAttrs[attr] = self.specParams[attr]

        video.appendChildWithArgs('model', type=self.device, **sourceAttrs)
        return video


class Watchdog(Base):
    __slots__ = ('address',)

    def __init__(self, *args, **kwargs):
        super(Watchdog, self).__init__(*args, **kwargs)

        if not hasattr(self, 'specParams'):
            self.specParams = {}

    def getXML(self):
        """
        Create domxml for a watchdog device.

        <watchdog model='i6300esb' action='reset'>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x05'
           function='0x0'/>
        </watchdog>
        """
        m = self.createXmlElem(self.type, None, ['address'])
        m.setAttrs(model=self.specParams.get('model', 'i6300esb'),
                   action=self.specParams.get('action', 'none'))
        return m


class Memory(Base):
    __slots__ = ('address', 'size', 'node')

    def __init__(self, conf, log, **kwargs):
        super(Memory, self).__init__(conf, log, **kwargs)
        # we get size in mb and send in kb
        self.size = int(kwargs.get('size')) * 1024
        self.node = kwargs.get('node')

    def getXML(self):
        """
        <memory model='dimm'>
            <target>
                <size unit='KiB'>524287</size>
                <node>1</node>
            </target>
        </memory>
        """

        mem = self.createXmlElem('memory', None)
        mem.setAttrs(model='dimm')
        target = self.createXmlElem('target', None)
        mem.appendChild(target)
        size = self.createXmlElem('size', None)
        size.setAttrs(unit='KiB')
        size.appendTextNode(str(self.size))
        target.appendChild(size)
        node = self.createXmlElem('node', None)
        node.appendTextNode(str(self.node))
        target.appendChild(node)

        return mem
