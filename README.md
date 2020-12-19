# statusfall

Statusfall displays SNMP data as a waterfall. Good values are green, bad are red. The upper part is shifted down by 1 pixel at intervals. The middle and the lower section are shifted down at longer intervals.

Statusfall creates periodically a new png picture file that presents the status. In addition to the picture, a basic html file and 2 additional data files are created. The purpose is the display in a web browser with reloads of the image at regular intervals and also some textual explanation of the columns. Hence, the configuration <statusFile> should point to a place the webserver can read.

## Installation

The python file can be installed anywhere. It takes an optional argument for a configuration file, with the default pointing to statusfall.yaml.
Hence, they python script can be stored at a bin directory, with the configuration at an etc. The snmp agents should support version 2c.

## Configuration

The configuration is stored in a YAML file with the fields have the following meanings:

| Field | Meaning |
|-------|---------|
| Interval | update frequency in seconds |
| upper | height of the upper section |
| div1 | the middle section is shifted down each <div1> shifts of the upper section |
| middle | height of the middle section |
| div2 | lower section shifts each <div2> shifts of the middle section |
| lower | height of the lower section |
| statusFile | the basename for the html, picture and and text files |
| hosts | a list of host configuration |
  
### Host configuration

| Field | Meaning |
|-------|---------|
| host  | ip address or hostname |
| community | the community string for reading those values using version 2c |
| watch | the SNMP variables to watch |

### Watch configuration 

| Field | Meaning |
|-------|---------|
| oid | snmp object identifier |
| type | defines how the return value is treated |
| description | the string that will be displayed in the web gui |
| min | minimal value |
| max | maximal value |
| error | oid for an error indication related to this variable |
| msg | oid for the status message |

### Type

At the moment, only "gauge" and "count" types are supported. Error oids must have value 1 for error and 0 for no error. The msg oid must return a text.
When the keyword "floating" is used, the maximum and minimum values are adjusted based on the returned values. The size of the counter value is determined based on the highest observed value. If the keyword "reserve" is used, then opposite color values are used - typical for *free space* and similar.

Recognized keywords for type: floating gauge count reverse



## Run

use it in a systemd service file or in an /etc/init.d with

*python3 statusfall.py statusfall.yaml*

## Observe

Open the generated *statusfall.html* in a web browser.
