#!/usr/bin/env python
import os
import re
import logging
from dotenv import load_dotenv
import yaml
from netmiko import ConnectHandler
from typing import Optional

# Configure logging to output progress messages to the console.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def check_power_status(output_power: str) -> bool:
    """
    Check the power command output.
    Returns True if all power supplies are "Normal", otherwise returns False.
    
    Expected format for each power line (columns separated by whitespace):
      PowerID  State  Mode  Current  Voltage  Power
    """
    lines = output_power.splitlines()
    pattern = re.compile(r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$")
    for line in lines:
        match = pattern.match(line)
        if match:
            # Unpack the captured groups (power_id, state, mode, current, voltage, power)
            _, state, _, _, _, _ = match.groups()
            if state.lower() != "normal":
                logging.info(f"Detected abnormal power status in line: '{line.strip()}'")
                return False
    return True

def check_fan_status(output_fan: str) -> bool:
    """
    Check the fan command output.
    Returns True if all fans are "Normal", otherwise returns False.
    
    Expected "display fan" output example:
    
        Slot 1:
         Fan 1:
          State                  : Normal
          Airflow Direction      : Port-to-power
          Preferred Airflow Direction : Port-to-power
         Fan 2:
          State                  : Fault
          Airflow Direction      : Port-to-power
          Preferred Airflow Direction : Port-to-power
    
    This function processes the output line by line, detecting each fan block and reading the "State" line.
    """
    lines = output_fan.splitlines()
    current_fan = None  # Stores current fan number in a block
    
    for line in lines:
        stripped = line.strip()
        # Detect the start of a fan block, e.g., "Fan 1:"
        fan_match = re.match(r"^Fan\s+(\d+):", stripped, re.IGNORECASE)
        if fan_match:
            current_fan = fan_match.group(1)
            continue
        # Look for the "State" line inside a fan block
        if current_fan and "state" in stripped.lower() and ":" in stripped:
            parts = stripped.split(":", 1)
            if len(parts) >= 2:
                state_value = parts[1].strip()
                if state_value.lower() != "normal":
                    logging.info(f"Detected abnormal fan status for Fan {current_fan}: {state_value}")
                    return False
            # Reset current_fan after processing its state
            current_fan = None
    return True

def write_results_to_file(filename: str, power_messages: list, fan_messages: list) -> None:
    """
    Write aggregated power and fan error messages to a file.
    The output file will have a [Power] section (if there are any power errors)
    and a [Fan] section (if there are any fan errors).
    If the target directory does not exist, it is created.
    """
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logging.info(f"Created directory: {directory}")
    
    logging.info(f"Writing results to {filename} ...")
    with open(filename, "w") as f:
        if power_messages:
            f.write("[Power]\n")
            for msg in power_messages:
                f.write(msg + "\n")
        if fan_messages:
            f.write("[Fan]\n")
            for msg in fan_messages:
                f.write(msg + "\n")
    logging.info("Writing complete.")

def main_actual() -> None:
    """
    Actual mode:
    Connects to each switch using Netmiko, executes the required commands,
    and checks the outputs.
    If a check fails, a generic error message is recorded for that host.
    The results are written to "check_output/actual_result.txt".
    """
    logging.info("Starting actual mode...")
    load_dotenv()
    username = os.getenv("ACCOUNT")
    password = os.getenv("PASSWORD")
    
    with open("target_switch.yaml", "r") as f:
        data = yaml.safe_load(f)
    ip_list = data["IPv4"]
    hostname_list = data["hostname"]

    actual_power_errors = []
    actual_fan_errors = []

    for ip, hostname in zip(ip_list, hostname_list):
        logging.info(f"Connecting to {hostname} ({ip}) ...")
        device = {
            "device_type": "hp_comware",  # Adjust based on your device's platform
            "ip": ip,
            "username": username,
            "password": password,
        }
        try:
            net_connect = ConnectHandler(**device)
            logging.info(f"Executing 'display power' on {hostname} ...")
            power_output = net_connect.send_command("display power")
            logging.info(f"Executing 'display fan' on {hostname} ...")
            fan_output = net_connect.send_command("display fan")
            
            power_ok = check_power_status(power_output)
            fan_ok = check_fan_status(fan_output)
            
            if not power_ok:
                actual_power_errors.append(f"{hostname} ({ip}) - Power fail")
            if not fan_ok:
                actual_fan_errors.append(f"{hostname} ({ip}) - Fan fail")
            
            net_connect.disconnect()
            logging.info(f"Finished processing {hostname} ({ip}).")
        except Exception as e:
            logging.error(f"Connection to {hostname} ({ip}) failed: {e}")

    write_results_to_file("check_output/actual_status_check_output/actual_result.txt", actual_power_errors, actual_fan_errors)
    logging.info("Actual mode complete.")

def main_simulation() -> None:
    """
    Simulation mode:
    Reads switch IP and hostname from a YAML file, then for each switch, reads simulated
    power and fan outputs from text files.
    If a check fails, a generic error message is recorded for that host.
    The results are written to "check_output/simulation_result.txt".
    """
    logging.info("Starting simulation mode...")
    with open("target_switch.yml", "r") as f:
        data = yaml.safe_load(f)
    ip_list = data["IPv4"]
    hostname_list = data["hostname"]

    sim_power_errors = []
    sim_fan_errors = []

    for ip, hostname in zip(ip_list, hostname_list):
        logging.info(f"Processing simulation files for {hostname} ({ip}) ...")
        power_file = f"simulation/POWER/{hostname}_power.txt"
        fan_file = f"simulation/FAN/{hostname}_fan.txt"
        try:
            with open(power_file, "r") as pf:
                power_output = pf.read()
            with open(fan_file, "r") as ff:
                fan_output = ff.read()

            power_ok = check_power_status(power_output)
            fan_ok = check_fan_status(fan_output)
            
            if not power_ok:
                sim_power_errors.append(f"{hostname} ({ip}) - Power fail")
            if not fan_ok:
                sim_fan_errors.append(f"{hostname} ({ip}) - Fan fail")
        except Exception as e:
            logging.error(f"Failed to read simulation file for {hostname} ({ip}): {e}")

    write_results_to_file("check_output/simulation_status_check_output/simulation_result.txt", sim_power_errors, sim_fan_errors)
    logging.info("Simulation mode complete.")


if __name__ == "__main__":
    # Uncomment one of the following based on which mode you want to run:
    # main_actual()
    main_simulation()
