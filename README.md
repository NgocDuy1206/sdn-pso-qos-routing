# QoS Routing & Network Traffic Monitoring in SDN using PSO

This repository contains the source code for my Graduation Thesis project at VNU University of Engineering and Technology (VNU-UET).

## 📌 Project Overview
A Software-Defined Networking (SDN) solution designed to monitor real-time network traffic, identify performance bottlenecks, and optimize Quality of Service (QoS) routing constraints using the **Particle Swarm Optimization (PSO)** algorithm.

## 🚀 Key Features
* **Traffic Monitoring:** Real-time packet flow capture and link utilization analysis using OpenFlow.
* **Dynamic Rerouting:** Automated rerouting under high-load or anomalous conditions to prevent service degradation.
* **PSO Optimization:** Particle Swarm Optimization algorithm applied for multi-constraint QoS route selection and dynamic load balancing.

## 🛠 Tech Stack & Tools
* **SDN Controller:** Ryu Controller
* **Network Emulator:** Mininet
* **Programming Languages:** Python, Bash Shell
* **Protocols & Concepts:** OpenFlow, TCP/IP, QoS Routing, Heuristic Optimization

## 📂 Repository Structure
* `ryu_controller/` : Python scripts for Ryu controller logic and PSO algorithm.
* `mininet_topology/` : Custom network topologies for Mininet simulation.
* `requirements.txt` : Python dependencies required for running the project.

## ⚙️ How to Run
1. Clone the repository:
   ```bash
   git clone [https://github.com/NgocDuy1206/sdn-pso-qos-routing](https://github.com/NgocDuy1206/sdn-pso-qos-routing)
   cd sdn-pso-qos-routing
