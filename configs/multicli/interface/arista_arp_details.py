"""
Arista eos Interface Details
Author: Mohammad Zaman
Email: mohammad.zaman@nokia.com

This code is a plugin for SR Linux CLI that provides detailed information about physical network interfaces in Arista format,
        Arista command: show arp 
        SRLinux command: show arpnd arp-entries
        Current usage on SRLinux: show eos arp

        This plugin will be updated to exact Arista CLI in 25.3.2 and 24.10.4
"""

from srlinux import strings
from srlinux.data import ColumnFormatter, Data, Alignment, Formatter, print_line
from srlinux.data.utilities import Percentage
from srlinux.location import build_path
from srlinux.mgmt.cli.cli_plugin import CliPlugin
from srlinux.mgmt.cli.key_completer import KeyCompleter
from srlinux.schema import FixedSchemaRoot
from srlinux.syntax import Syntax
from datetime import datetime, timedelta

class ArpDetails(object):
    
    def _get_syntax_arp(self):        
        result = Syntax('arp', help='Show IPv4 arp entries report')
        result.add_named_argument('interface', default='*', suggestions=KeyCompleter(path=self._interface_path))
        result.add_named_argument('subinterface', default='*', suggestions=KeyCompleter(path=self._subinterface_path))
        result.add_named_argument('ipv4-address', default='*',
                                suggestions=KeyCompleter(path=lambda arguments: self._ipv4_address_path(arguments)))
        return result

    def _get_arp_schema(self, v4):
        root = FixedSchemaRoot()
        if v4:
            root.add_child('neighbor',
                        keys=['Address'],
                        fields=['Age_sec', 'Hardware_Addr', 'Interface'])
        else:
            root.add_child('neighbor',
                        keys=['Subinterface', 'Age (sec)', 'Neighbor'],
                        fields=[
                            'Origin',
                            'Link layer address',
                            'Current state',
                            'Next state change',
                            'Is Router'
                        ])
        return root
    
    def _interface_path(self, arguments):
        return build_path('/interface[name=*]')

    def _subinterface_path(self, arguments):
        return build_path(
            '/interface[name={name}]/subinterface[index=*]',
            name=arguments.get('interface'))

    def _ipv4_address_path(self, arguments, wildcard=True):
        return build_path(
            '/interface[name={name}]/subinterface[index={index}]/ipv4/arp/neighbor[ipv4-address={address}]',
            name=arguments.get('interface'),
            index=arguments.get('subinterface'),
            address='*' if wildcard else arguments.get('ipv4-address')
        )

    def _ipv6_address_path(self, arguments, wildcard=True):
        return build_path(
            '/interface[name={name}]/subinterface[index={index}]/ipv6/neighbor-discovery/neighbor[ipv6-address={address}]',
            name=arguments.get('interface'),
            index=arguments.get('subinterface'),
            address='*' if wildcard else arguments.get('ipv6-address')
        )

    def _fetch_state(self, state, arguments, v4):
        path = self._ipv4_address_path(
            arguments, False) if v4 else self._ipv6_address_path(arguments, False)

        return state.server_data_store.stream_data(path, recursive=True)

    def _init_members(self):
        self._total_entries = 0
        self._static_entries = 0
        self._dynamic_entries = 0

    def _populate_data(self, data, server_data, v4):
        self._init_members()
        data.synchronizer.flush_fields(data)

        for interface in server_data.interface.items():
            self._add_subinterface(data, interface.name,
                                   interface.subinterface, v4)

        data.synchronizer.flush_children(data.neighbor)
        return data
    
    def _add_subinterface(self, data, interface_name, server_data, v4):
        for subinterface in server_data.items():
            self._add_neighbor(data, interface_name, subinterface.index,
                               subinterface.ipv4.get().arp.get().neighbor if v4
                               else subinterface.ipv6.get().neighbor_discovery.get().neighbor, v4)
    
    @staticmethod
    def convert_mac(mac):
            mac = mac.replace(":", "").replace("-", "").lower()
            if len(mac) != 12:
                return mac
            return f"{mac[0:4]}.{mac[4:8]}.{mac[8:12]}"

    @staticmethod
    def convert_iso_to_hms(iso_time_str):
        dt = datetime.fromisoformat(iso_time_str.replace("Z", "+00:00"))  # Convert to datetime object
        return dt.strftime("%H:%M:%S")  # Format as hh:mm:ss

    

    def _add_neighbor(self, data, interface_name, subinterface_index, server_data, v4):   
        for neighbor in server_data.items():
            if v4:
                # Create the neighbor row using the new schema.
                child = data.neighbor.create(neighbor.ipv4_address)
                self._total_entries += 1

                # Compute the "Age (sec)" as a natural relative time string.
                expiration_time = neighbor.expiration_time
                # time_remaining = strings.natural_relative_time(expiration_time) if expiration_time else "0:00:00"
                child.age_sec = self.convert_iso_to_hms(expiration_time)
                # The "Hardware Addr" column.
                child.hardware_addr = self.convert_mac(neighbor.link_layer_address)
                child.interface = f"{interface_name}.{subinterface_index}" if subinterface_index != interface_name else interface_name
                child.synchronizer.flush_fields(child)
            else:
                child = data.neighbor.create(interface_name, subinterface_index, neighbor.ipv6_address)
                self._total_entries += 1
                expiration_time = neighbor.next_state_time
                time_remaining = strings.natural_relative_time(expiration_time) if expiration_time else None
                child.link_layer_address = neighbor.link_layer_address
                child.next_state_change = time_remaining
                child.current_state = neighbor.current_state
                child.is_router = neighbor.is_router
                child.synchronizer.flush_fields(child)

    
    def _set_formatters(self, data, v4):
        if v4:
            data.set_formatter('/neighbor',
                            ColumnFormatter(ancestor_keys=True,
                                            borders=0,
                                            widths=[15, 10, 15, 20],
                                            horizontal_alignment={
                                                'address': Alignment.Left,
                                                'age_sec': Alignment.Center,
                                                'hardware_addr': Alignment.Center,
                                                'interface': Alignment.Center,
                },
                                            )
                            )
        else:
            ip_length = 39
            column_widths = [
                Percentage(10),
                ip_length,
                Percentage(10),
                Percentage(20),
            ]
            if not v4:
                column_widths.extend([Percentage(10), Percentage(20), Percentage(10)])
            data.set_formatter('/neighbor',
                            ColumnFormatter(ancestor_keys=True,
                                            borders=0,
                                            widths=column_widths,
                                            horizontal_alignment={
                                                'Subinterface': Alignment.Right,
                                                'Neighbor': Alignment.Right,
                                                'Age (sec)': Alignment.Right
                                            }
                                            )
                            )

    def _ipv4_variant(self, arguments):
        return arguments.node.name == 'arp'

    def print(self, state, arguments, output, **_kwargs): 
        v4 = self._ipv4_variant(arguments)
        server_data = self._fetch_state(state, arguments, v4)
        result = Data(arguments.schema)
        self._set_formatters(result, v4)

        with output.stream_data(result):
            self._populate_data(result, server_data, v4)


class SummaryFormatter(Formatter):

    def iter_format(self, entry, max_width):
        yield print_line(max_width, '-')
        yield from self._format_entry(entry, max_width)
        yield print_line(max_width, '-')

    def _format_entry(self, entry, max_width):
        yield f'  Total entries : {entry.total_entries} ({entry.static_entries} static, {entry.dynamic_entries} dynamic)'
