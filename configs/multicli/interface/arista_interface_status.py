"""
Arista eos Interface Status
Author: Mohammad Zaman
Email: mohammad.zaman@nokia.com

This code is a plugin for SR Linux CLI that provides detailed information about physical network interfaces in Arista format,
        Arista command: show interface status
        SRLinux command: show interface  brief
        Current usage on SRLinux: show eos interface status

        This plugin will be updated to exact Arista CLI in 25.3.2 and 24.10.4
"""

from srlinux.data import ColumnFormatter, Data, Borders, ColumnFormatter, Alignment
from srlinux.location import build_path
from srlinux.schema import FixedSchemaRoot
from srlinux.syntax import Syntax


class InterfaceStatus(object):
    def get_syntax_status(self):
        result = Syntax('status', help='Show arista interface status for interfaces')
        return result

    def get_data_schema(self):
        root = FixedSchemaRoot()
        root.add_child(
            'IfBrief',
            key='Port',
            fields=['Name', 'Status', 'vlan', 'Duplex', 'Speed', 'Type'],
        )
        return root

    def print(self, state, arguments, output, **_kwargs):
        serve_data = self._stream_data(state, arguments)
        result = Data(arguments.schema)
        self._set_formatters(result)
        with output.stream_data(result):
            self._populate_data(result, serve_data)

    def _stream_data(self, state, arguments):
        path = build_path('/interface[name={name}]', name=arguments.get('interface', 'name'))
        return state.server_data_store.stream_data(path, recursive=False, include_container_children=True)

    def _populate_data(self, data, serve_data):
        data.synchronizer.flush_fields(data)
        for interface in serve_data.interface.items():
            child = data.ifbrief.create(interface.name)
            child.name = interface.description
            child.status = "notconnected"
            if interface.oper_state == "up":
                child.status = "connected"                
            child.vlan = interface.vlan_tagging
            try:
                child.duplex = interface.ethernet.get().duplex_mode
            except: 
                child.duplex = "full"
            child.speed = interface.ethernet.get().port_speed
            child.type = interface.transceiver.get().ethernet_pmd
            child.synchronizer.flush_fields(child)
        data.synchronizer.flush_children(data.ifbrief)

    def _set_formatters(self, interface_data):
        # data = interface_data
        formatter = ColumnFormatter(
            borders=Borders.Nothing,
            horizontal_alignment={
                'Port': Alignment.Left,
                'Name': Alignment.Left,
                'Status': Alignment.Right,
                'vlan': Alignment.Center,
                'Duplex': Alignment.Center,
                'Speed': Alignment.Center,
                'Type': Alignment.Left
            },
            widths={
                'Port': 14,
                'Name': 10,
                'Status': 14,
                'vlan': 10,
                'Duplex': 10,
                'Speed': 10,
                'Type': 10
            }

        )
        interface_data.set_formatter('/IfBrief', formatter)