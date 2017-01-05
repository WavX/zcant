"""
ZCANT main GUI code.

---------------
Myotisoft ZCANT
Copyright (C) 2012-2017 Myotisoft LLC, all rights reserved.
You may use, distribute, and modify this code under the terms of the MIT License.
"""


from __future__ import division

import os
import os.path
import sys
import json
import webbrowser
from fnmatch import fnmatch
from bisect import bisect

import wx

import numpy as np

import matplotlib
matplotlib.interactive(True)
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
import matplotlib.ticker
import matplotlib.gridspec
from matplotlib.cm import get_cmap, ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.widgets import Cursor, RectangleSelector

from zcant import __version__
from zcant import print_timing
from zcant.anabat import extract_anabat, AnabatFileWriter
from zcant.conversion import wav2zc

import logging
log = logging.getLogger(__name__)


np.seterr(all='warn')  # switch to 'raise' and NumPy will fail fast on calculation errors


CONF_FNAME = os.path.expanduser('~/.myotisoft/zcant.ini')


CMAP_SEQ  = ['Blues', 'BuGn', 'BuPu', 'GnBu', 'Greens', 'Greys', 'Oranges', 'OrRd', 'PuBu', 'PuBuGn', 'PuRd', 'Purples', 'RdPu', 'Reds', 'YlGn', 'YlGnBu', 'YlOrBr', 'YlOrRd']
CMAP_SEQ2 = ['afmhot', 'autumn', 'bone', 'cool', 'copper', 'gist_heat', 'gray', 'hot', 'pink', 'spring', 'summer', 'winter']
CMAP_DIV  = ['BrBG', 'bwr', 'coolwarm', 'PiYG', 'PRGn', 'PuOr', 'RdBu', 'RdGy', 'RdYlBu', 'RdYlGn', 'Spectral', 'seismic']
CMAP_MISC = ['gist_earth', 'terrain', 'ocean', 'gist_stern', 'brg', 'CMRmap', 'cubehelix', 'gnuplot', 'gnuplot2', 'gist_ncar', 'nipy_spectral', 'jet', 'rainbow', 'gist_rainbow', 'hsv', 'flag', 'prism']
CMAPS = CMAP_SEQ + CMAP_SEQ2 + CMAP_DIV + CMAP_MISC


def title_from_path(path):
    root, fname = os.path.split(path)
    root, parent = os.path.split(root)
    root, gparent = os.path.split(root)
    if gparent:
        title = '%s %s %s %s %s' % (gparent, os.sep, parent, os.sep, fname)
    elif parent:
        title = '%s %s %s' % (parent, os.sep, fname)
    else:
        title = fname
    return title.replace('_', ' ')


def beep():
    sys.stdout.write('\a')
    sys.stdout.flush()


class ZcantMainFrame(wx.Frame):

    WAV_THRESHOLD_DELTA = 0.25  # RMS ratio
    HPF_DELTA = 2.5             # kHz

    def __init__(self, parent, title='Myotisoft ZCANT '+__version__):
        wx.Frame.__init__(self, parent, title=title, size=(640,480))

        # Application State - set initial defaults, then read state from conf file
        self.dirname = ''
        self.filename = ''

        self.is_compressed = True
        self.is_linear_scale = True
        self.use_smoothed_slopes = False
        self.display_cursor = False
        self.cmap = 'jet'
        self.harmonics = {'0.5': False, '1': True, '2': False, '3': False}

        self.wav_threshold = 1.5
        self.wav_divratio = 16
        self.hpfilter = 17.5
        self.wav_interpolation = False

        self.window_secs = None
        self.window_start = 0.0

        self.read_conf()

        # Initialize and load...
        log.debug('Initializing GUI...')
        self.init_gui()
        log.debug('GUI initialized.')

        if self.dirname and self.filename:
            try:
                self.load_file(self.dirname, self.filename)
            except Exception, e:
                log.exception('Failed opening default file: %s', os.path.join(self.dirname, self.filename))
        else:
            log.debug('No valid dirname/filename; doing nothing.')

    def init_gui(self):
        self.plotpanel = None

        self.init_menu()

        self.init_toolbar()

        # Main layout
        #self.main_grid = wx.FlexGridSizer(rows=2)

        # Control Panel
        #self.control_panel = wx.Panel(self)
        #self.threshold_spinctl = wx.SpinCtrl(self, value=str(self.wav_threshold))  #, pos=(150, 75), size=(60, -1))
        #self.threshold_spinctl.SetRange(0.0, 10.0)

        # Status Bar
        self.statusbar = self.CreateStatusBar()

        self.init_keybindings()

    def init_menu(self):
        # Menu Bar
        menu_bar = wx.MenuBar()

        # -- File Menu
        file_menu = wx.Menu()
        open_item = file_menu.Append(wx.ID_OPEN, '&Open', ' Open a zero-cross file')
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        about_item = file_menu.Append(wx.ID_ABOUT, '&About', ' Information about this program')
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, 'E&xit', ' Terminate this program')
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        menu_bar.Append(file_menu, '&File')

        # -- View Menu
        view_menu = wx.Menu()

        view_menu.AppendSeparator()
        log_item = view_menu.AppendRadioItem(wx.ID_ANY, 'Log Scale', ' Logarithmic frequency scale')
        self.Bind(wx.EVT_MENU, self.on_scale_toggle, log_item)
        linear_item = view_menu.AppendRadioItem(wx.ID_ANY, 'Linear Scale', ' Linear frequency scale')
        self.Bind(wx.EVT_MENU, self.on_scale_toggle, linear_item)
        log_item.Check(not self.is_linear_scale)
        linear_item.Check(self.is_linear_scale)

        view_menu.AppendSeparator()
        smooth_item = view_menu.AppendCheckItem(wx.ID_ANY, 'Smooth Slopes', 'Smooth out noisy slope values')
        self.Bind(wx.EVT_MENU, self.on_smooth_slope_toggle, smooth_item)
        smooth_item.Check(self.use_smoothed_slopes)

        view_menu.AppendSeparator()
        cursor_item = view_menu.AppendCheckItem(wx.ID_ANY, 'Display Cursor', 'Display horizontal and vertical cursors')
        self.Bind(wx.EVT_MENU, self.on_cursor_toggle, cursor_item)
        cursor_item.Check(self.display_cursor)

        view_menu.AppendSeparator()
        h05_item = view_menu.AppendCheckItem(wx.ID_ANY, '1/2 Harmonic', ' One-half harmonic')
        self.Bind(wx.EVT_MENU, lambda e: self.on_harmonic_toggle('0.5'), h05_item)
        h1_item =  view_menu.AppendCheckItem(wx.ID_ANY, 'Fundamental',  ' Fundamental frequency')
        h2_item =  view_menu.AppendCheckItem(wx.ID_ANY, '2nd Harmonic', ' 2nd harmonic')
        self.Bind(wx.EVT_MENU, lambda e: self.on_harmonic_toggle('2'), h2_item)
        h3_item =  view_menu.AppendCheckItem(wx.ID_ANY, '3nd Harmonic', ' 3rd harmonic')
        self.Bind(wx.EVT_MENU, lambda e: self.on_harmonic_toggle('3'), h3_item)
        menu_bar.Append(view_menu, '&View')

        # -- Conversion Menu
        convert_menu = wx.Menu()
        convert_menu.AppendSeparator()
        div4_item = convert_menu.AppendRadioItem(wx.ID_ANY, 'Div 4', ' 1/4 frequency division ratio')
        div4_item.Check(self.wav_divratio == 4)
        self.Bind(wx.EVT_MENU, lambda e: self.on_divratio_select(4), div4_item)
        div8_item = convert_menu.AppendRadioItem(wx.ID_ANY, 'Div 8', ' 1/8 frequency division ratio')
        div8_item.Check(self.wav_divratio == 8)
        self.Bind(wx.EVT_MENU, lambda e: self.on_divratio_select(8), div8_item)
        div16_item = convert_menu.AppendRadioItem(wx.ID_ANY, 'Div 16', ' 1/16 frequency division ratio')
        div16_item.Check(self.wav_divratio == 16)
        self.Bind(wx.EVT_MENU, lambda e: self.on_divratio_select(16), div16_item)
        div32_item = convert_menu.AppendRadioItem(wx.ID_ANY, 'Div 32', ' 1/32 frequency division ratio')
        div32_item.Check(self.wav_divratio == 32)
        self.Bind(wx.EVT_MENU, lambda e: self.on_divratio_select(32), div32_item)

        convert_menu.AppendSeparator()
        interpolation_item = convert_menu.AppendCheckItem(wx.ID_ANY, 'Interpolate', 'Interpolate between .WAV samples')
        self.Bind(wx.EVT_MENU, self.on_interpolation_toggle, interpolation_item)
        interpolation_item.Check(self.wav_interpolation)
        menu_bar.Append(convert_menu, '&Conversion')

        # -- Help Menu
        help_menu = wx.Menu()
        keybindings_item = help_menu.Append(wx.ID_ANY, 'Keyboard Shortcuts', 'View list of keyboard shortcuts')
        self.Bind(wx.EVT_MENU, lambda e: self.on_view_keybindings, keybindings_item)
        website_item = help_menu.Append(wx.ID_ANY, 'Myotisoft Website', 'Visit the Myotisoft website')
        self.Bind(wx.EVT_MENU, lambda e: webbrowser.open_new_tab('http://myotisoft.com'), website_item)
        menu_bar.Append(help_menu, '&Help')

        self.SetMenuBar(menu_bar)

    def init_toolbar(self):
        # Nav Toolbar
        tool_bar = self.CreateToolBar(wx.TB_TEXT)
        open_item = tool_bar.AddLabelTool(wx.ID_ANY, 'Open',
                                          wx.Bitmap('resources/icons/file-8x.png'),
                                          shortHelp='Open')
        self.Bind(wx.EVT_TOOL, self.on_open, open_item)
        tool_bar.AddSeparator()
        prev_dir = tool_bar.AddLabelTool(wx.ID_ANY, 'Prev Folder',
                                         wx.Bitmap('resources/icons/chevron-left-8x.png'),
                                         shortHelp='Prev folder',
                                         longHelp='Open the previous folder (or use the `{` key)')
        self.Bind(wx.EVT_TOOL, self.on_prev_dir, prev_dir)
        prev_file = tool_bar.AddLabelTool(wx.ID_ANY, 'Prev File',
                                          wx.Bitmap('resources/icons/caret-left-8x.png'),
                                          shortHelp='Prev file',
                                          longHelp='Open the previous file in this folder (or use `[` key)')
        self.Bind(wx.EVT_TOOL, self.on_prev_file, prev_file)
        next_file = tool_bar.AddLabelTool(wx.ID_ANY, 'Next File',
                                          wx.Bitmap('resources/icons/caret-right-8x.png'),
                                          shortHelp='Next file',
                                          longHelp='Open the next file in this folder (or use the `]` key)')
        self.Bind(wx.EVT_TOOL, self.on_next_file, next_file)
        next_dir = tool_bar.AddLabelTool(wx.ID_ANY, 'Next Folder',
                                         wx.Bitmap('resources/icons/chevron-right-8x.png'),
                                         shortHelp='Next folder',
                                         longHelp='Open the next folder (or use the `}` key)')
        self.Bind(wx.EVT_TOOL, self.on_next_dir, next_dir)
        tool_bar.AddSeparator()
        toggle_compressed = tool_bar.AddLabelTool(wx.ID_ANY, 'Compressed', wx.Bitmap(
            'resources/icons/audio-spectrum-8x.png'),
                                                  shortHelp='Toggle compressed',
                                                  longHelp='Toggle compressed view on/off (or use the `c` key)')
        self.Bind(wx.EVT_TOOL, self.on_compressed_toggle, toggle_compressed)
        tool_bar.AddSeparator()
        # self.SetToolBar(tool_bar)
        tool_bar.Realize()

    def init_keybindings(self):
        # Key Bindings
        # TODO: move all these IDs to global scope and reuse them in menubar
        prev_file_id, next_file_id, prev_dir_id, next_dir_id = wx.NewId(), wx.NewId(), wx.NewId(), wx.NewId()
        compressed_id, scale_id, cmap_id, cmap_back_id = wx.NewId(), wx.NewId(), wx.NewId(), wx.NewId()
        threshold_up_id, threshold_down_id, hpfilter_up_id, hpfilter_down_id = wx.NewId(), wx.NewId(), wx.NewId(), wx.NewId()
        win_forward_id, win_back_id, win_zoom_in, win_zoom_out, win_zoom_off = wx.NewId(), wx.NewId(), wx.NewId(), wx.NewId(), wx.NewId()
        save_file_id, save_image_id = wx.NewId(), wx.NewId()

        self.Bind(wx.EVT_MENU, self.on_prev_file, id=prev_file_id)
        self.Bind(wx.EVT_MENU, self.on_next_file, id=next_file_id)
        self.Bind(wx.EVT_MENU, self.on_prev_dir, id=prev_dir_id)
        self.Bind(wx.EVT_MENU, self.on_next_dir, id=next_dir_id)
        self.Bind(wx.EVT_MENU, self.on_compressed_toggle, id=compressed_id)
        self.Bind(wx.EVT_MENU, self.on_scale_toggle, id=scale_id)
        self.Bind(wx.EVT_MENU, self.on_cmap_switch, id=cmap_id)
        self.Bind(wx.EVT_MENU, self.on_cmap_back, id=cmap_back_id)
        self.Bind(wx.EVT_MENU, self.on_threshold_up, id=threshold_up_id)
        self.Bind(wx.EVT_MENU, self.on_threshold_down, id=threshold_down_id)
        self.Bind(wx.EVT_MENU, self.on_hpfilter_up, id=hpfilter_up_id)
        self.Bind(wx.EVT_MENU, self.on_hpfilter_down, id=hpfilter_down_id)
        self.Bind(wx.EVT_MENU, self.on_save_file, id=save_file_id)
        self.Bind(wx.EVT_MENU, self.on_save_image, id=save_image_id)
        self.Bind(wx.EVT_MENU, self.on_win_forward, id=win_forward_id)
        self.Bind(wx.EVT_MENU, self.on_win_back, id=win_back_id)
        self.Bind(wx.EVT_MENU, self.on_zoom_in, id=win_zoom_in)
        self.Bind(wx.EVT_MENU, self.on_zoom_out, id=win_zoom_out)
        self.Bind(wx.EVT_MENU, self.on_zoom_off, id=win_zoom_off)

        a_table = wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, ord('['),  prev_file_id),
            (wx.ACCEL_NORMAL, wx.WXK_F3, prev_file_id),
            (wx.ACCEL_NORMAL, ord(']'),  next_file_id),
            (wx.ACCEL_NORMAL, wx.WXK_F4, next_file_id),

            (wx.ACCEL_SHIFT, ord('['), prev_dir_id),  # {
            (wx.ACCEL_SHIFT, ord(']'), next_dir_id),  # }

            (wx.ACCEL_NORMAL, wx.WXK_SPACE, compressed_id),
            (wx.ACCEL_NORMAL, ord('l'), scale_id),

            (wx.ACCEL_NORMAL, ord('c'), cmap_id),
            (wx.ACCEL_SHIFT,  ord('c'), cmap_back_id),

            (wx.ACCEL_NORMAL, wx.WXK_UP,   threshold_up_id),
            (wx.ACCEL_NORMAL, wx.WXK_DOWN, threshold_down_id),

            (wx.ACCEL_SHIFT, wx.WXK_UP,   hpfilter_up_id),
            (wx.ACCEL_SHIFT, wx.WXK_DOWN, hpfilter_down_id),

            (wx.ACCEL_NORMAL, wx.WXK_RIGHT, win_forward_id),
            (wx.ACCEL_NORMAL, wx.WXK_LEFT,  win_back_id),
            (wx.ACCEL_SHIFT,  ord('='), win_zoom_in),   # +
            (wx.ACCEL_NORMAL, ord('='), win_zoom_in),
            (wx.ACCEL_SHIFT,  ord('-'), win_zoom_out),  # -
            (wx.ACCEL_NORMAL, ord('-'), win_zoom_out),
            (wx.ACCEL_NORMAL, ord('0'), win_zoom_off),

            (wx.ACCEL_CMD, ord('p'), save_image_id),
            (wx.ACCEL_CMD, ord('s'), save_file_id),
        ])
        self.SetAcceleratorTable(a_table)

    def on_save_image(self, event):
        if not self.plotpanel or not self.filename or not self.dirname:
            return
        imagename = os.path.splitext(os.path.join(self.dirname, self.filename))[0] + '.png'
        log.debug('Saving image: %s', imagename)
        try:
            self.plotpanel.figure.savefig(imagename)
        except Exception, e:
            log.exception('Failed saving image: %s', imagename)

    @print_timing
    def on_save_file(self, event):
        # For now, we will only save a converted .WAV as Anabat file
        if not self.filename.lower().endswith('.wav'):
            return
        outdir = os.path.join(self.dirname, '_ZCANT_Converted')
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        outfname = self.filename[:-4]+'.zc'
        outpath = os.path.join(outdir, outfname)
        timestamp = self._metadata.get('timestamp', None)
        log.debug('Saving %s ...', outpath)

        with AnabatFileWriter(outpath) as out:
            out.write_header(timestamp, self.wav_divratio, species='', note1='Myotisoft ZCANT', note2='')  # TODO
            time_indexes_us = self._times * 1000000
            intervals_us = np.diff(time_indexes_us)
            intervals_us = intervals_us.astype(int)  # TODO: round before int cast; consider casting before diff for performance
            out.write_intervals(intervals_us)

    def on_about(self, event):
        log.debug('about: %s', event)
        dlg = wx.MessageDialog(self, 'A boring Zero-Cross Viewer!', 'About ZCANT', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def on_view_keybindings(self, event):
        log.debug('keybindings', event)
        # TODO display keybindings

    def on_exit(self, event):
        log.debug('exit: %s', event)
        self.Close(True)

    def on_open(self, event):
        log.debug('open: %s', event)
        dlg = wx.FileDialog(self, 'Choose a file', self.dirname, '', 'Anabat files|*.*|Anabat files|*.zc|Wave files|*.wav', wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetFilename()
            dirname = dlg.GetDirectory()
            log.debug('open: %s', os.path.join(dirname, filename))
            self.load_file(dirname, filename)
            self.save_conf()
        dlg.Destroy()

    def save_conf(self):
        conf_dir = os.path.split(CONF_FNAME)[0]
        try:
            if not os.path.isdir(conf_dir):
                os.mkdir(conf_dir)
        except IOError, e:
            logging.exception('Failed attempting to create conf directory: %s', conf_dir)

        conf = {
            'dirname':    self.dirname,
            'filename':   self.filename,
            'compressed': self.is_compressed,
            'linear':     self.is_linear_scale,
            'colormap':   self.cmap,
            'harmonics':  self.harmonics,
            'smooth_slopes': self.use_smoothed_slopes,
            'interpolation': self.wav_interpolation,
        }
        with open(CONF_FNAME, 'w') as outf:
            logging.debug('Writing conf file: %s', CONF_FNAME)
            outf.write(json.dumps(conf, indent=2))

    def read_conf(self):
        if not os.path.isfile(CONF_FNAME):
            return False
        with open(CONF_FNAME, 'r') as inf:
            logging.debug('Reading conf file: %s', CONF_FNAME)
            conf = json.load(inf)
            self.dirname = conf.get('dirname', '')
            self.filename = conf.get('filename', '')
            self.is_compressed = conf.get('compressed', True)
            self.is_linear_scale = conf.get('linear', True)
            self.cmap = conf.get('colormap', 'jet')
            self.use_smoothed_slopes = conf.get('smooth_slopes', False)
            self.wav_interpolation = conf.get('interpolation', True)
            harmonics = conf.get('harmonics', {'0.5': False, '1': True, '2': False, '3': False})

    def listdir(self, dirname):
        """Produce a list of supported filenames in the specified directory"""
        return [fname for fname in sorted(os.listdir(dirname), key=lambda s: s.lower()) if (
                fnmatch(fname, '*.??#') or fnmatch(fname.lower(), '*.zc') or fnmatch(fname.lower(), '*.wav')
                ) and not fname.startswith('._')   # MacOSX meta-files on a FAT filesystem
        ]

    def on_prev_file(self, event):
        log.debug('prev_file: %s', event)
        files = self.listdir(self.dirname)
        try:
            i = files.index(self.filename)
        except ValueError:
            i = bisect(files, self.filename)  # deleted out from under us?
        if i <= 0:
            return beep()  # we're at the start of the list
        self.load_file(self.dirname, files[i-1])
        self.save_conf()

    def on_next_file(self, event):
        log.debug('next_file: %s', event)
        files = self.listdir(self.dirname)
        try:
            i = files.index(self.filename)
        except ValueError:
            i = bisect(files, self.filename)  # deleted out from under us?
        if i == len(files) - 1:
            return beep()  # we're at the end of the list
        self.load_file(self.dirname, files[i+1])
        self.save_conf()

    def on_prev_dir(self, event):
        log.debug('prev_dir: %s', event)
        parent, current = os.path.split(self.dirname)
        siblings = [p for p in sorted(os.listdir(parent)) if os.path.isdir(os.path.join(parent, p))]
        try:
            i = siblings.index(current)
        except ValueError:
            i = bisect(siblings, current)  # deleted out from under us?
        if i <= 0:
            return beep()  # we're at the start of the list
        newdir = os.path.join(parent, siblings[i-1])
        files = self.listdir(newdir)
        if not files:
            return beep()  # no anabat files in next dir
        self.load_file(newdir, files[0])
        self.save_conf()

    def on_next_dir(self, event):
        log.debug('next_dir: %s', event)
        parent, current = os.path.split(self.dirname)
        siblings = [p for p in sorted(os.listdir(parent)) if os.path.isdir(os.path.join(parent, p))]
        try:
            i = siblings.index(current)
        except ValueError:
            i = bisect(siblings, current)  # deleted out from under us?
        if i == len(siblings) - 1:
            return beep()  # we're at the end of the list
        newdir = os.path.join(parent, siblings[i+1])
        files = self.listdir(newdir)
        if not files:
            return beep()  # no anabat files in next dir
        self.load_file(newdir, files[0])
        self.save_conf()

    def on_zoom_in(self, event):
        if self.window_secs and self.window_secs <= 1.0 / 256:
            return  # max zoom is 1/256 sec (4 ms)

        if self.window_secs is None:
            self.window_secs = 2.0  # jump immediately to 2 secs... revisit this
        else:
            self.window_secs /= 2
        self.reload_file()

    def on_zoom_out(self, event):
        if self.window_secs and self.window_secs >= 32:
            return  # min zoom is 32 sec (arbitrary)

        if self.window_secs is None:
            return
        self.window_secs *= 2
        self.reload_file()

    def on_zoom_off(self, event):
        self.window_secs = None
        self.window_start = 0.0
        self.reload_file()

    def on_win_forward(self, event):
        if self.window_secs is None:
            return
        window_start = self.window_start + (self.window_secs / 5)
        if window_start >= self._times[-1]:
            window_start = self._times[-1] - self.window_secs
        if window_start < 0:
            window_start = 0  # very short files?
        log.debug('shifting window forward to %.1f sec', window_start)
        self.window_start = window_start
        self.reload_file()

    def on_win_back(self, event):
        if self.window_secs is None:
            return
        window_start = self.window_start - self.window_secs / 5
        if window_start < 0:
            window_start = 0
        log.debug('shifting window backward to %.1f sec', window_start)
        self.window_start = window_start
        self.reload_file()

    def extract(self, path):
        """Extract (times, freqs, amplitudes, metadata) from supported filetypes"""
        ext = os.path.splitext(path)[1].lower()
        if ext.endswith('#') or ext == '.zc':
            return extract_anabat(path, hpfilter_khz=self.hpfilter)
        elif ext == '.wav':
            return wav2zc(path, divratio=self.wav_divratio,
                          threshold_factor=self.wav_threshold,
                          hpfilter_khz=self.hpfilter,
                          interpolation=self.wav_interpolation)
        else:
            raise Exception('Unknown file type: %s', path)

    def reload_file(self):
        """Re-plot current file without reloading from disk"""
        return self.plot(self._times, self._freqs, self._amplitudes, self._metadata)

    def load_file(self, dirname, filename):
        """Called to either load a new file fresh, or load the current file when we've made
        changes that necessitate re-parsing the original file itself."""
        log.debug('\n\nload_file:  %s  %s', dirname, filename)

        if filename != self.filename:
            # reset some file-specific state
            self.window_start = 0.0

        path = os.path.join(dirname, filename)
        if not path:
            return

        wx.BeginBusyCursor()

        try:
            times, freqs, amplitudes, metadata = self.extract(path)

            metadata['path'] = path
            metadata['filename'] = filename
            log.debug('    %s:  times: %d  freqs: %d', filename, len(times), len(freqs))

            self.plot(times, freqs, amplitudes, metadata)

            self.dirname, self.filename = dirname, filename
            self._times, self._freqs, self._amplitudes, self._metadata = times, freqs, amplitudes, metadata  # only set on success
        except Exception, e:
            log.exception('Barfed loading file: %s', path)

        wx.EndBusyCursor()

    def windowed_view(self, times, freqs, amplitudes):
        # FIXME: don't jump to 2sec window if recording is < 2secs
        if len(times) < 2:
            return times, freqs, amplitudes

        if times[-1] - self.window_start >= self.window_secs:
            #log.info('NORMAL')
            window_from, window_to = bisect(times, self.window_start), bisect(times, self.window_start + self.window_secs)
        elif self.window_secs >= times[-1]:
            #log.info('WINDOW TOO BIG')
            window_from, window_to = 0, len(times)-1  # window is bigger than file
        else:
            #log.info('END OF FILE')
            window_from, window_to = bisect(times, times[-1] - self.window_secs), len(times)-1  # panned to the end

        times, freqs = times[window_from:window_to], freqs[window_from:window_to]
        amplitudes = amplitudes[window_from:window_to] if amplitudes is not None else None

        # because times is sparse, we need to fill in edge cases (unfortunately np.insert, np.append copy rather than view)
        if len(times) == 0 or times[0] > self.window_start:
            times, freqs = np.insert(times, 0, self.window_start), np.insert(freqs, 0, self.window_start)
            amplitudes = np.insert(amplitudes, 0, self.window_start) if amplitudes is not None else None
        if times[-1] < self.window_start + self.window_secs:
            times, freqs = np.append(times, self.window_start + self.window_secs), np.append(freqs, 0)  # this is wrong for END OF FILE case
            amplitudes = np.append(amplitudes, 0) if amplitudes is not None else None  # ?

        log.debug('%.1f sec window:  times: %d  freqs: %d', self.window_secs, len(times), len(freqs))
        return times, freqs, amplitudes

    def plot(self, times, freqs, amplitudes, metadata):
        title = title_from_path(metadata.get('path', ''))
        conf = dict(compressed=self.is_compressed, colormap=self.cmap, scale='linear' if self.is_linear_scale else 'log',
                    filter_markers=(self.hpfilter,), harmonics=self.harmonics,
                    smooth_slopes=self.use_smoothed_slopes, display_cursor=self.display_cursor)

        if self.window_secs is not None:
            times, freqs, amplitudes = self.windowed_view(times, freqs, amplitudes)

        try:
            panel = ZeroCrossPlotPanel(self, times, freqs, amplitudes, name=title, config=conf)
            panel.Show()

            self.update_statusbar(times, freqs, metadata)

            if self.plotpanel:
                self.plotpanel.Destroy()  # out with the old, in with the new
            self.plotpanel = panel

        except Exception, e:
            log.exception('Failed plotting %s', metadata.get('filename', ''))

    def _pretty_window_size(self):
        if self.window_secs is None:
            return 'whole file'
        elif self.window_secs >= 1.0:
            return str(self.window_secs) + ' secs'
        else:
            fractional_secs = int(round(1 / self.window_secs))
            ms = int(round(self.window_secs * 1000))
            return '1/%d sec (%d ms)' % (fractional_secs, ms)

    def update_statusbar(self, times, freqs, metadata):
        timestamp = metadata.get('timestamp', None) or metadata.get('date', '????-??-??')
        if hasattr(timestamp, 'strftime'):
            timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        species = ', '.join(metadata.get('species', [])) or '?'
        min_ = np.amin(freqs) / 1000 if len(freqs) else 0  # TODO: non-zero freqs only
        max_ = np.amax(freqs) / 1000 if len(freqs) else 0
        divratio = metadata.get('divratio', self.wav_divratio)
        info = 'HPF: %.1f kHz   Sensitivity: %.2f RMS   Div: %d   View: %s' % (self.hpfilter, self.wav_threshold, divratio, self._pretty_window_size())
        self.statusbar.SetStatusText(
            '%s     Dots: %5d     Fmin: %5.1f kHz     Fmax: %5.1f kHz     Species: %s       [%s]'
            % (timestamp, len(freqs), min_, max_, species, info)
        )

    def on_compressed_toggle(self, event):
        log.debug('toggling compressed view (%s)', not self.is_compressed)
        self.is_compressed = not self.is_compressed
        if not self.filename:
            return
        self.reload_file()
        self.save_conf()

    def on_scale_toggle(self, event):
        log.debug('toggling Y scale (%s)', 'linear' if self.is_linear_scale else 'log')
        self.is_linear_scale = not self.is_linear_scale
        self.reload_file()
        self.save_conf()

    def on_smooth_slope_toggle(self, event):
        log.debug('smoothing...' if not self.use_smoothed_slopes else 'un-smoothing...')
        self.use_smoothed_slopes = not self.use_smoothed_slopes
        self.reload_file()
        self.save_conf()  # FIXME: persist this state

    def on_cursor_toggle(self, event):
        log.debug('displaying cursor...' if not self.display_cursor else 'hiding cursor...')
        self.display_cursor = not self.display_cursor
        self.reload_file()
        self.save_conf()  # FIXME: persist this state

    def on_harmonic_toggle(self, harmonic):
        self.harmonics[harmonic] = not self.harmonics.get(harmonic, False)
        self.reload_file()
        self.save_conf()

    def on_divratio_select(self, divratio):
        self.wav_divratio = divratio
        self.load_file(self.dirname, self.filename)
        self.save_conf()

    def on_interpolation_toggle(self, event):
        log.debug('interpolating .WAV samples' if not self.wav_interpolation else 'disabling .WAV interpolation')
        self.wav_interpolation = not self.wav_interpolation
        self.load_file(self.dirname, self.filename)
        self.save_conf()

    def on_cmap_switch(self, event):
        i = CMAPS.index(self.cmap) + 1
        i %= len(CMAPS) - 1
        self.cmap = CMAPS[i]
        log.debug('switching to colormap: %s', self.cmap)
        self.reload_file()
        self.save_conf()

    def on_cmap_back(self, event):
        i = CMAPS.index(self.cmap) - 1
        i %= len(CMAPS) - 1
        self.cmap = CMAPS[i]
        log.debug('switching to colormap: %s', self.cmap)
        self.reload_file()
        self.save_conf()

    def on_threshold_up(self, event):
        self.wav_threshold += self.WAV_THRESHOLD_DELTA
        log.debug('increasing threshold to %.1f x RMS', self.wav_threshold)
        self.load_file(self.dirname, self.filename)
        self.save_conf()

    def on_threshold_down(self, event):
        if self.wav_threshold < self.WAV_THRESHOLD_DELTA:
            return
        self.wav_threshold -= self.WAV_THRESHOLD_DELTA
        log.debug('decreasing threshold to %.1f x RMS', self.wav_threshold)
        self.load_file(self.dirname, self.filename)
        self.save_conf()

    def on_hpfilter_up(self, event):
        self.hpfilter += self.HPF_DELTA
        log.debug('increasing high-pass filter to %.1f KHz', self.hpfilter)
        self.load_file(self.dirname, self.filename)
        self.save_conf()

    def on_hpfilter_down(self, event):
        if self.hpfilter < self.HPF_DELTA:
            return
        self.hpfilter -= self.HPF_DELTA
        log.debug('decreasing high-pass filter to %.1f KHz', self.hpfilter)
        self.load_file(self.dirname, self.filename)
        self.save_conf()


class PlotPanel(wx.Panel):
    """Base class for embedding matplotlib in wx.

    The PlotPanel has a Figure and a Canvas. OnSize events simply set a
    flag, and the actual resizing of the figure is triggered by an Idle event.
    See: http://wiki.scipy.org/Matplotlib_figure_in_a_wx_panel
    """
    # TODO: look into this implementation: http://fides.fe.uni-lj.si/pyopus/doc/wxmplplot.html
    #       http://sukhbinder.wordpress.com/2013/12/19/matplotlib-with-wxpython-example-with-panzoom-functionality/

    def __init__(self, parent, color=None, dpi=None, **kwargs):
        from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
        from matplotlib.figure import Figure

        # initialize Panel
        if 'id' not in kwargs.keys():
            kwargs['id'] = wx.ID_ANY
        if 'style' not in kwargs.keys():
            kwargs['style'] = wx.NO_FULL_REPAINT_ON_RESIZE

        self.parent = parent
        wx.Panel.__init__(self, parent, **kwargs)

        # initialize matplotlib stuff
        self.figure = Figure(None, dpi, frameon=True, tight_layout=False)
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.SetColor(color)

        # Wire up mouse event
        #self.canvas.mpl_connect('motion_notify_event', self.on_mouse_motion)
        #self.canvas.Bind(wx.EVT_ENTER_WINDOW, self.ChangeCursor)

        self._SetSize()
        self.draw()

        self._resizeflag = False

        self.Bind(wx.EVT_IDLE, self._onIdle)
        self.Bind(wx.EVT_SIZE, self._onSize)

    def SetColor(self, rgbtuple=None):
        """Set figure and canvas colours to be the same."""
        if rgbtuple is None:
            rgbtuple = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE).Get()
        clr = [c/255. for c in rgbtuple]
        self.figure.set_facecolor(clr)
        self.figure.set_edgecolor(clr)
        self.canvas.SetBackgroundColour(wx.Colour(*rgbtuple))

    def _onSize(self, event):
        self._resizeflag = True

    def _onIdle(self, event):
        if self._resizeflag:
            self._resizeflag = False
            self._SetSize()

    def _SetSize(self):
        pixels = tuple(self.parent.GetClientSize())
        inches = float(pixels[0])/self.figure.get_dpi(), float(pixels[1])/self.figure.get_dpi()
        self.SetSize(pixels)
        self.canvas.SetSize(pixels)
        self.figure.set_size_inches(inches)
        log.debug('_SetSize  DPI: %s  pixels: %s  inches: %s', self.figure.get_dpi(), pixels, inches)

    def on_mouse_motion(self, event):
        pass  # abstract, to be overridden by child classes

    def draw(self):
        pass  # abstract, to be overridden by child classes


@print_timing
def smooth(slopes):
    """
    Smooth slope values to account for the fact that zero-cross conversion may be noisy.
    :param slopes: slope values
    :return:
    TODO: smooth individual pulses independently so we don't smooth across their boundaries
    """
    WINDOW_SIZE = 3  # hard-coded for now
    if slopes.size == 0:
        return np.array([])
    elif slopes.size == 1:
        return np.array([0.0])
    elif slopes.size == 2:
        return np.array([0.0, 0.0])
    elif slopes.size == 3:
        return np.array([0.0, 0.0, 0.0])
    # Rather than true convolution, we use a much faster cumulative sum solution
    # http://stackoverflow.com/a/11352216
    # http://stackoverflow.com/a/34387987
    slopes = np.where(np.isnan(slopes), 0, slopes)  # replace NaN values
    cumsum = np.cumsum(np.insert(slopes, 0, 0))
    smoothed = (cumsum[WINDOW_SIZE:] - cumsum[:-WINDOW_SIZE]) / WINDOW_SIZE
    # smoothed is missing element at start and end, so fake 'em
    smoothed = np.insert(smoothed, 0, smoothed[0])
    smoothed = np.insert(smoothed, -1, smoothed[-1])
    return smoothed


@print_timing
def slopes(x, y, smooth_slopes=False):
    """
    Produce an array of slope values in octaves per second.
    We very, very crudely try to compensate for the jump between pulses, but don't deal well with noise.
    :param x:
    :param y:
    :return:
    """
    if not len(x) or not len(y):
        return np.array([])
    elif len(x) == 1:
        return np.array([0.0])

    if not np.any(y):
        y_octaves = y
    else:
        # calculation for difference wil be same in Hz or kHz, so no need to convert
        y_octaves = np.log2(y)
        y_octaves[np.isnan(y_octaves)] = 0.0
    slopes = np.diff(y_octaves) / np.diff(x)
    slopes = np.append(slopes, slopes[-1])  # FIXME: hack for final dot (instead merge slope(signal[1:]) and slope(signal[:-1])
    slopes = -1 * slopes  # Analook inverts slope so we do also
    log.debug('Smax: %.1f OPS   Smin: %.1f OPS', np.amax(slopes) or -9999, np.amin(slopes) or -9999)
    slopes[slopes < -5000] = 0.0  # super-steep is probably noise or a new pulse
    slopes[slopes > 10000] = 0.0  # TODO: refine these magic boundary values!
    slopes[np.isnan(slopes)] = 0.0

    if smooth_slopes:
        # FIXME: rather than smoothing after the fact, can we simply calculate slope initially across every 2nd element?
        slopes = smooth(slopes)

    return slopes


class ZeroCrossPlotPanel(PlotPanel):

    SLOPE_MAX = 1000  #750  # highest slope value (oct/sec) of our color scale; TODO: make scale log-based?
    SLOPE_MIN = 0  #-SLOPE_MAX

    config = {  # DEFAULTS
        'freqminmax': (15, 100),   # min and max frequency to display KHz
        'scale': 'linear',         # linear | log
        'markers': (25, 40),       # reference lines kHz
        'filter_markers': (20.0,), # filter lines kHz
        'compressed': False,       # compressed view (True) or realtime (False)
        'smooth_slopes': True,     # smooth out noisy slope values
        'interpolate': True,       # interpolate between WAV samples
        'display_cursor': False,   # display horiz and vert cursor lines
        'colormap': 'jet',         # named color map
        'dot_sizes': (40, 12, 2),  # dot display sizes in points (max, default, min)
        'harmonics': {'0.5': False, '1': True, '2': False, '3': False},
    }

    def __init__(self, parent, times, freqs, amplitudes, config=None, **kwargs):
        self.times = times if len(times) else np.array([0.0])
        self.freqs = freqs if len(freqs) else np.array([0.0])
        dot_max, dot_default, dot_min = self.config['dot_sizes']
        if amplitudes is not None:
            self.amplitudes = amplitudes if len(amplitudes) else np.array([0.0])
            # normalize amplitude values to display point size
            log.debug(' orig. amp  max: %.1f  min: %.1f', np.max(self.amplitudes), np.min(self.amplitudes))
            self.scaled_amplitudes = (amplitudes / np.amax(self.amplitudes)) * (dot_max - dot_min) + dot_min
            log.debug('scaled amp  max: %.1f  min: %.1f', np.max(self.scaled_amplitudes) if len(self.scaled_amplitudes) else 0.0, np.min(self.scaled_amplitudes) if len(self.scaled_amplitudes) else 0.0)
        else:
            self.amplitudes = np.ones(len(freqs), dtype=np.int8)
            self.scaled_amplitudes = np.full(len(freqs), dot_default, dtype=np.int8)

        self.name = kwargs.get('name', '')
        if config:
            self.config.update(config)

        self.slopes = slopes(self.times, self.freqs, smooth_slopes=self.config['smooth_slopes'])
        self.freqs = self.freqs / 1000  # convert Hz to KHz  (the /= operator doesn't work here?!)

        PlotPanel.__init__(self, parent, **kwargs)

        self.SetColor((0xF0, 0xF0, 0xF0))  # outside border color

    @print_timing
    def draw(self):
        # TODO: recycle the figure with `self.fig.clear()` rather than creating new panel and figure each refresh!

        gs = matplotlib.gridspec.GridSpec(1, 3, width_ratios=[85, 5, 10], wspace=0.025)

        # --- Main dot scatter plot ---
        self.dot_plot = self.figure.add_subplot(gs[0])

        miny, maxy = self.config['freqminmax']
        plot_kwargs = dict(cmap=self.config['colormap'],
                           vmin=self.SLOPE_MIN, vmax=self.SLOPE_MAX,  # vmin/vmax define where we scale our colormap
                           c=self.slopes, s=self.scaled_amplitudes,   # dot color and size
                           linewidths=0.0,
                           )

        def plot_harmonics(x):
            """Reusable way to plot harmonics from different view types"""
            if self.config['harmonics']['0.5']:
                self.dot_plot.scatter(x, self.freqs/2, alpha=0.2, **plot_kwargs)
            if self.config['harmonics']['2']:
                self.dot_plot.scatter(x, self.freqs*2, alpha=0.2, **plot_kwargs)
            if self.config['harmonics']['3']:
                self.dot_plot.scatter(x, self.freqs*3, alpha=0.2, **plot_kwargs)

        if len(self.freqs) < 2:
            dot_scatter = self.dot_plot.scatter([], [])  # empty set
        elif not self.config['compressed']:
            # Realtime View
            plot_harmonics(self.times)
            dot_scatter = self.dot_plot.scatter(self.times, self.freqs, **plot_kwargs)
            self.dot_plot.set_xlim(self.times[0], self.times[-1])
            self.dot_plot.set_xlabel('Time (sec)')
        else:
            # Compressed (pseudo-Dot-Per-Pixel) View
            x = range(len(self.freqs))
            plot_harmonics(x)
            dot_scatter = self.dot_plot.scatter(x, self.freqs, **plot_kwargs)
            self.dot_plot.set_xlim(0, len(x))
            self.dot_plot.set_xlabel('Dot Count')

        self.dot_plot.set_title(self.name)
        try:
            self.dot_plot.set_yscale(self.config['scale'])  # FIXME: fails with "Data has no positive values" error
        except ValueError:
            log.exception('Failed setting log scale (exception caught)')
            log.error('\ntimes: %s\nfreqs: %s\nslopes: %s', self.times, self.freqs, self.slopes)
        self.dot_plot.set_ylim(miny, maxy)
        self.dot_plot.set_ylabel('Frequency (KHz)')

        self.dot_plot.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        minytick = miny if miny % 10 == 0 else miny + 10 - miny % 10  # round up to next 10kHz tick
        maxytick = maxy if maxy % 10 == 0 else maxy + 10 - maxy % 10
        ticks = range(minytick, maxytick+1, 10)   # labels every 10kHz
        self.dot_plot.get_yaxis().set_ticks(ticks)

        self.dot_plot.grid(axis='y', which='both')

        for freqk in self.config['markers']:
            self.dot_plot.axhline(freqk, color='r')

        for freqk in self.config['filter_markers']:
            self.dot_plot.axhline(freqk, color='b', linestyle='--')

        # draw X and Y cursor; this may beform better if we can use Wx rather than MatPlotLib, see `wxcursor_demo.py`
        if self.config['display_cursor']:
            self.cursor1 = Cursor(self.dot_plot, useblit=True, color='black', linewidth=1)

        # experimental rectangle selection
        def onselect(eclick, erelease):
            """eclick and erelease are matplotlib events at press and release"""
            x1, y1 = eclick.xdata, eclick.ydata
            x2, y2 = erelease.xdata, erelease.ydata
            print ' Select  (%.3f,%.1f) -> (%.3f,%.1f)  button: %d' % (x1, y1, x2, y2, eclick.button)
            slope = (np.log2(y2) - np.log2(y1)) / (x2 - x1)  # FIXME: we don't support compressed mode here!
            print '         slope: %.1f oct/sec  (%.1f kHz / %.3f sec)' % (slope, y2 - y1, x2 - x1)

        self.selector = RectangleSelector(self.dot_plot, onselect, drawtype='box')
        #connect('key_press_event', toggle_selector)

        # --- Colorbar plot ---
        cbar_plot = self.figure.add_subplot(gs[1])
        cbar_plot.set_title('Slope')
        try:
            cbar = self.figure.colorbar(dot_scatter, cax=cbar_plot, ticks=[])
        except TypeError, e:
            # colorbar() blows up on empty set
            sm = ScalarMappable(cmap=self.config['colormap'])  # TODO: this should probably share colormap code with histogram
            sm.set_array(np.array([self.SLOPE_MIN, self.SLOPE_MAX]))
            cbar = self.figure.colorbar(sm, cax=cbar_plot, ticks=[])
        cbar.ax.set_yticklabels([])

        # --- Hist plot ---

        hist_plot = self.figure.add_subplot(gs[2])
        hist_plot.set_title('Freqs')

        bin_min, bin_max = self.config['freqminmax']
        bin_size = 2  # khz  # TODO: make this configurable
        bin_n = int((bin_max - bin_min) / bin_size)
        n, bins, patches = hist_plot.hist(self.freqs, weights=self.amplitudes,
                                          range=self.config['freqminmax'], bins=bin_n,
                                          orientation='horizontal')
        hist_plot.set_yscale(self.config['scale'])
        hist_plot.set_ylim(miny, maxy)
        hist_plot.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())

        # color histogram bins
        cmap = ScalarMappable(cmap=self.config['colormap'], norm=Normalize(vmin=self.SLOPE_MIN, vmax=self.SLOPE_MAX))
        for bin_start, bin_end, patch in zip(bins[:-1], bins[1:], patches):
            bin_mask = (bin_start <= self.freqs) & (self.freqs < bin_end)
            bin_slopes = self.slopes[bin_mask]
            slope_weights = self.scaled_amplitudes[bin_mask]
            avg_slope = np.average(bin_slopes, weights=slope_weights) if bin_slopes.any() else 0
            #avg_slope = np.median(bin_slopes) if bin_slopes.any() else 0
            patch.set_facecolor(cmap.to_rgba(avg_slope))

        hist_plot.yaxis.set_ticks(ticks)
        hist_plot.yaxis.tick_right()
        hist_plot.grid(axis='y', which='both')
        hist_plot.xaxis.set_ticks([])

        for freqk in self.config['markers']:
            hist_plot.axhline(freqk, color='r')

        for freqk in self.config['filter_markers']:
            hist_plot.axhline(freqk, color='b', linestyle='--')

        # draw Y cursor
        if self.config['display_cursor']:
            self.cursor3 = Cursor(hist_plot, useblit=True, color='black', linewidth=1, vertOn=False, horizOn=True)


    # def on_mouse_motion(self, event):
    #     if event.inaxes:
    #         x, y = event.xdata, event.ydata
    #         print '%.1fkHz, %.1f' % (y, x)