# synthetic-human-agent-e9
NTU X ST Engineering Hackathon 2026

## About our peoject

 - Created for *NTU X ST Engineering Hackathon 2026*
 - A tool that runs and performs routine office tasks.

## Features

 - The agent itself is completely (at least for now) pre-programmed.

## Architecture

The file structure is as follows:

### **./core**
 
These files define and implement the essential APIs (e.g. cursor controll) to
simulate human behaviors. More specifically:

 - core/process.py: provides appropriate means of launching a specific app
*without* being marked as suspicous by the monitor systems.

 - core/timing.py: provides APIs to simulate lags and pauses to simulate human
behavior. Ideally, they are just safe wrappers of time.sleep().

 - core/ui.py: provides everything associated with UI operations, such as moving
 cursors, resizing windows, typing texts... 

### **./tasks**

This directory stores *task*s. a *task* is an abstraction of a series of adjacent
microbehaviors. For example, a "search_something_in_edge" task is consist of several
microbehaviors: 

 1. get the coordinate of Edge icon;
 2. move and click that icon;
 3. click the search bar + think for 3 seconds;
 4. type in something + enter;
 5. scroll up and down...

In principle, every microbehavior can be done by 1~3 APIs provided by ./core files. 
Thi allows us to compose endless tasks using their combinations. (This is the power
of decoupling!)

### **main.py**

`main.py` is the agent's entry point. In the current Hello World run, it calls
`DefaultTask` to prepare the desktop and then runs `HelloWorldTask` once. The
task sequence and examples for calling the UI helpers are documented in
[docs/helloworld-task.md](docs/helloworld-task.md).


