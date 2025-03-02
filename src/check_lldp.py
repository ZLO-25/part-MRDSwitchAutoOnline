#!/usr/bin/env python
import os
import re
import logging
from dotenv import load_dotenv
import yaml
from netmiko import ConnectHandler
from typing import Optional, List

# Configure logging to output progress messages to the console.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def load_yaml(yaml_str: str) -> List[dict]:
    """
    Load port mapping information from a YAML string.

    Args:
        yaml_str: YAML formatted string.

    Returns:
        A list of mapping dictionaries under the key 'port_mappings'.
    """
    data = yaml.safe_load(yaml_str)
    return data['port_mappings']

def parse_lldp_output(lldp_str: str) -> dict:
    """
    Parse the LLDP neighbor output and return a dictionary keyed by local interface.
    
    Each key's value is a dictionary containing the neighbor system name and remote port:
      { local_interface: {'neighbor': system_name, 'remote_port': port_id}, ... }
      
    Args:
        lldp_str: The output string from "display lldp neighbor list".
        
    Returns:
        A dictionary of parsed LLDP neighbor information.
    """
    lldp_mapping = {}
    lines = lldp_str.strip().splitlines()
    for line in lines:
        line = line.strip()
        # Skip headers, divider lines, and summary lines.
        if (not line or set(line) == {"-"} or 
            "Local Interface" in line or 
            "Total number of neighbors:" in line):
            continue

        # Split the line into parts.
        parts = line.split()
        if len(parts) < 4:
            continue
        
        local_interface = parts[0]
        # Only process lines where the local interface appears to be valid.
        # For example, valid interfaces for our mapping start with "Ten-GigabitEthernet"
        if not local_interface.startswith("Ten-GigabitEthernet"):
            continue
        
        port_id = parts[2]
        system_name = " ".join(parts[3:])
        lldp_mapping[local_interface] = {'neighbor': system_name, 'remote_port': port_id}
    return lldp_mapping

def compare_mappings(yaml_list: List[dict], lldp_mapping: dict) -> List[str]:
    """
    Compare the port mapping defined in the YAML with the parsed LLDP output.
    Also reports any extra LLDP entries not defined in the YAML.

    Args:
        yaml_list: A list of port mapping entries from the YAML.
        lldp_mapping: A dictionary from parse_lldp_output().

    Returns:
        A list of mismatch messages.
    """
    mismatches = []
    expected_ports = set()

    # Compare expected entries from YAML.
    for entry in yaml_list:
        this_port = entry['this_port']
        expected_ports.add(this_port)
        expected_neighbor_hostname = entry['neighbor_hostname']
        expected_neighbor_port = entry['neighbor_port']
        if this_port not in lldp_mapping:
            mismatches.append(f"Local interface {this_port} missing in LLDP output.")
        else:
            actual = lldp_mapping[this_port]
            if actual['neighbor'] != expected_neighbor_hostname:
                mismatches.append(
                    f"{this_port}: Expected neighbor hostname '{expected_neighbor_hostname}', got '{actual['neighbor']}'."
                )
            if actual['remote_port'] != expected_neighbor_port:
                mismatches.append(
                    f"{this_port}: Expected neighbor port '{expected_neighbor_port}', got '{actual['remote_port']}'."
                )
    
    # Report extra LLDP entries that are not defined in the YAML mapping.
    for local_interface in lldp_mapping:
        if local_interface not in expected_ports:
            extra = lldp_mapping[local_interface]
            mismatches.append(
                f"Extra LLDP entry found: {local_interface} -> Neighbor: '{extra['neighbor']}', Port: '{extra['remote_port']}'."
            )
    
    return mismatches

def get_lldp_output_from_switch(ip: str, username: str, password: str) -> Optional[str]:
    """
    Connect to a switch using Netmiko and retrieve the LLDP neighbor output.

    Args:
        ip: The IP address of the switch.
        username: Username for authentication.
        password: Password for authentication.

    Returns:
        The output string from "display lldp neighbor list", or None if connection fails.
    """
    device = {
        "device_type": "hp_comware",  # Adjust as needed for your device
        "ip": ip,
        "username": username,
        "password": password,
    }
    try:
        logging.info(f"Connecting to switch at {ip} for LLDP check...")
        net_connect = ConnectHandler(**device)
        lldp_output = net_connect.send_command("display lldp neighbor list")
        net_connect.disconnect()
        logging.info(f"Successfully retrieved LLDP output from {ip}.")
        return lldp_output
    except Exception as e:
        logging.error(f"Failed to get LLDP output from {ip}: {e}")
        return None

def compare_mappings_from_switch(yaml_list: List[dict], ip: str, username: str, password: str) -> List[str]:
    """
    Connect to a switch and compare the LLDP neighbor output with the YAML mapping.

    Args:
        yaml_list: A list of port mapping entries for a given host from YAML.
        ip: The IP address of the switch.
        username: Username for authentication.
        password: Password for authentication.

    Returns:
        A list of mismatch messages.
    """
    lldp_output = get_lldp_output_from_switch(ip, username, password)
    if lldp_output is None:
        return [f"Failed to retrieve LLDP output from switch at {ip}."]
    lldp_mapping = parse_lldp_output(lldp_output)
    return compare_mappings(yaml_list, lldp_mapping)

def compare_mappings_from_file(yaml_list: List[dict], filename: str) -> List[str]:
    """
    Read LLDP neighbor output from a file and compare with the YAML mapping.

    Args:
        yaml_list: A list of port mapping entries for a given host from YAML.
        filename: The path to the file containing LLDP output.

    Returns:
        A list of mismatch messages.
    """
    try:
        with open(filename, "r") as f:
            lldp_output = f.read()
        lldp_mapping = parse_lldp_output(lldp_output)
        return compare_mappings(yaml_list, lldp_mapping)
    except Exception as e:
        logging.error(f"Failed to read LLDP output file {filename}: {e}")
        return [f"Failed to read LLDP output file {filename}: {e}"]

def write_results_to_file(filename: str, messages: List[str]) -> None:
    """
    Write a list of messages to a file. If the target directory does not exist, it is created.

    Args:
        filename: The output file path.
        messages: List of messages (mismatches) to write.
    """
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logging.info(f"Created directory: {directory}")
    
    logging.info(f"Writing results to {filename} ...")
    with open(filename, "w") as f:
        if messages:
            for msg in messages:
                f.write(msg + "\n")
        else:
            f.write("YAML port mapping matches LLDP output.\n")
    logging.info("Writing complete.")

def main():
    # Load the YAML mapping from target_switch.yml.
    logging.info("Loading YAML mapping from target_switch.yml ...")
    try:
        with open("target_switch.yml", "r") as f:
            data = yaml.safe_load(f)
        ip_list = data["IPv4"]
        hostname_list = data["hostname"]
        port_mappings_raw = data.get("port_mappings", [])
        logging.info("YAML mapping loaded successfully.")
    except Exception as e:
        logging.error(f"Failed to load YAML mapping from target_switch.yml: {e}")
        return

    # Convert the new YAML structure into a flat list of mapping dictionaries.
    flat_mappings = []
    for entry in port_mappings_raw:
        hostname = entry.get("switch_hostname", "")
        port_list = entry.get("local_port_to_neighbor", [])
        for item in port_list:
            parts = item.split(',')
            if len(parts) < 3:
                continue
            this_port = parts[0].strip()
            neighbor_port = parts[1].strip()
            neighbor_hostname = parts[2].strip()
            flat_mappings.append({
                "this_hostname": hostname,
                "this_port": this_port,
                "neighbor_port": neighbor_port,
                "neighbor_hostname": neighbor_hostname
            })

    # Mode 1: Actual connection via Netmiko.
    # (This block is commented out; uncomment if you wish to run actual mode)
    # load_dotenv()
    # username = os.getenv("ACCOUNT")
    # password = os.getenv("PASSWORD")
    # actual_mismatches = []
    # for ip, hostname in zip(ip_list, hostname_list):
    #     # Filter flat mappings for this host.
    #     host_mappings = [entry for entry in flat_mappings if entry["this_hostname"] == hostname]
    #     if not host_mappings:
    #         logging.info(f"No port mappings defined for {hostname}, skipping LLDP check.")
    #         continue
    #     logging.info(f"Starting LLDP check for {hostname} ({ip}) using actual connection...")
    #     mismatches = compare_mappings_from_switch(host_mappings, ip, username, password)
    #     for m in mismatches:
    #         actual_mismatches.append(f"{hostname} ({ip}) - {m}")
    # write_results_to_file("check_output/actual_lldp_check/actual_result.txt", actual_mismatches)

    # Mode 2: Simulation mode.
    simulation_mismatches = []
    for ip, hostname in zip(ip_list, hostname_list):
        # Filter flat mappings for this host.
        host_mappings = [entry for entry in flat_mappings if entry["this_hostname"] == hostname]
        if not host_mappings:
            logging.info(f"No port mappings defined for {hostname}, skipping simulation LLDP check.")
            continue
        sim_file = f"simulation/LLDP/{hostname}_lldp.txt"
        logging.info(f"Processing simulation file for {hostname} ({ip}) from {sim_file} ...")
        mismatches = compare_mappings_from_file(host_mappings, sim_file)
        for m in mismatches:
            simulation_mismatches.append(f"{hostname} ({ip}) - {m}")
    write_results_to_file("check_output/simulation_lldp_check/simulation_result.txt", simulation_mismatches)

if __name__ == "__main__":
    main()
