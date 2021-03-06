# Myotisoft ZCANT

ZCANT is a tool for analyzing bat echolocation calls. Specifically, it extracts the echolocation
signal using the zero-crossing technique pioneered by Chris Corben, with a few modern twists:

- Digital signal processing techniques are used to enhance the audio during the zero-cross
  extraction.

- Amplitude from the original full-spectrum signal is integrated into the zero-cross display
  visually, essentially providing the "best of both worlds".

- Slope, the most important derived parameter of a time/frequency zero-cross signal, is integrated
  into the display visually as color. You'll soon develop a synesthesia that lets you see the shape
  of a call by its colors.

![ZCANT Screenshot](/docs/images/zcant_screenshot.png?raw=true "ZCANT Screenshot")


## License

ZCANT is Free / Open Source Software, cross-platform, and written in the Python programming
language. It can serve as the base for your own bat acoustics software projects! See the file
`LICENSE.txt` for details of the MIT License.

Copyright (C) 2012-2017 by Myotisoft LLC <http://myotisoft.com>


## Requirements

- Python 2.7
- NumPy
- SciPy
- MatPlotLib 1.5.3 or 2.0.0+
- WxPython 3.0


## Installation

1. Download and install [Python 2.7](https://www.python.org/downloads/), or verify that your
   existing version is 2.7 with with `python --version`.

2. Install wxPython "classic" 3.0.2.0. See https://wiki.wxpython.org/How%20to%20install%20wxPython
   for details, or use the following direct links:
   [Window 32-bit](https://sourceforge.net/projects/wxpython/files/wxPython/3.0.2.0/wxPython3.0-win32-3.0.2.0-py27.exe/download)
   [Windows 64-bit](https://sourceforge.net/projects/wxpython/files/wxPython/3.0.2.0/wxPython3.0-win64-3.0.2.0-py27.exe/download)
   [Mac OSX](https://sourceforge.net/projects/wxpython/files/wxPython/3.0.2.0/wxPython3.0-osx-3.0.2.0-cocoa-py2.7.dmg/download)

3. Download the ZCANT source code, either by downloading the [latest ZCANT release .zip](https://github.com/riggsd/zcant/releases),
   or by cloning your own copy of the source repository with the commands:

    $> git clone https://github.com/riggsd/zcant.git  
    $> cd zcant

4. The remainder of the dependency libraries can be installed using `pip`:

    $> pip -r requirements.txt

5. Start ZCANT:

    $> python zcant.py


## Usage

Runtime settings which tweak the display of data are found under the `View` menu.

Settings which control how full-spectrum data is converted into zero-cross data are found under
the `Conversion` menu.

At this time, most functionality is controlled with your *keyboard*. Refer to the file 
`docs/keybindings.txt` for a full list of keybindings, but the following quick-start guide should
get you up and running:

* Use the `]` and `[` keys to navigate forward and backward (respectively) within a folder full of recordings.

* Use the `}` and `{` keys to navigate forward and backward (respectively) to different folders.
  This is most useful if your data is organized in folders by night, by sight, by species, etc.

* Use the `SPACE` key to toggle back and forth between realtime view and compressed (dot-per-pixel)
  view. The former is best for examining the relationship between echolocation pulses within a
  sequence or for viewing individual pulses in detail; the latter is best for examining the shape of
  many calls simultaneously.

* Use the `+` and `-` keys to zoom in or out (respectively) in time. Press `0` (zero) to jump back
  to "whole file" view. The first zoom jumps to a 2-second view; each zoom in or out is 1/2 or 2x
  the previous zoom.

* Use the `>` and `<` keys to scroll forward or backward (respectively) in time within a file.

* Use the `l` key to toggle back and forth between linear and logarithmic frequency scales.

* Use the `UP` and `DOWN` keys to increase the noise gate threshold (discard weaker noise, at the
  expense of possibly discarding weaker echolocation signal) or decrease the noise gate threshold 
  (show weaker signals, at the possible expense of showing more noise) (respectively). The noise
  gate threshold is expressed in terms of the root-mean-square (RMS) of the recording, which can be
  thought of as its "noise floor". A threshold of "1.5x RMS" means that only portions of the signal
  which are 150% of the noise floor will be displayed; weaker noise will be thrown out. The current
  threshold is displayed in the status bar at the bottom of the screen. (Default of 1.5x is a safe
  starting point for "clean" recordings, but should be increased if noise dots overwhelm
  echolocation pulses, or it may be decreased to more accurately reflect the high and low
  frequencies of echolocation pulses.)

* Use the `SHIFT+UP` and `SHIFT+DOWN` key combinations to raise or lower (respectively) the
  high-pass filter's (HPF) cutoff frequency. The HPF is a digital filter which removes low-frequency
  noise from the full-spectrum recording prior to zero-crossing; it is a steep, 6-pole filter,
  followed by a "brickwall filter" that removes any dots below the cutoff frequency *after*
  zero-crossing. This should be used to filter out any audible (non-bat) frequencies, but will
  remove bat echolocation signals if set too high. Setting the HPF to 0.0kHz will disable it
  entirely, so that the original file is zero-crossed in pristine state. The current HPF cutoff
  is displayed in the status bar at the bottom of the screen, and visually denoted by a dashed
  blue line. (Default is 17.5kHz, which will mask the occurance of some low-frequency North
  American bats.)

* Use `CMD+s` to save an Anabat-format file, or `CMD-p` to "print" a screenshot image in .PNG format.
  The saved Anabat-format files will be in a sub-folder named "_ZCANT_Converted".
 
* Delete a .WAV file with the `DELETE` key. Delete just the converted zero-cross file (but not the
  .WAV itself) with `SHIFT+DELETE`. Files are never truly deleted, they're moved into a sub-folder
  named "Deleted Files".


## Credits

ZCANT was written by David A. Riggs of [Myotisoft LLC](http://myotisoft.com). Inspiration for
zero-cross analysis of bat echolocation, as well as the Anabat file format by
[Chris Corben](http://users.lmi.net/corben/).

Free / Open Source software utilized: [Python](http://python.org), [NumPy](http://www.numpy.org/), 
[MatPlotLib](http://matplotlib.org/), and [wxPython](https://wxpython.org/) for the core of the
application. Sound playback thanks to the [sounddevice](https://python-sounddevice.readthedocs.io)
/ [PortAudio](http://www.portaudio.com/) library. Graphic icons by 
[Open Iconic](https://useiconic.com/open).
