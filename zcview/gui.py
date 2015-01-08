"""
ZCView GUI
"""

import os
import os.path
import math
from glob import glob
from fnmatch import fnmatch

import wx

import matplotlib
matplotlib.interactive(True)
matplotlib.use('WXAgg')

from zcview.anabat import extract_anabat

import logging
log = logging.getLogger(__name__)


def title_from_path(path):
    root, fname = os.path.split(path)
    root, parent = os.path.split(root)
    root, gparent = os.path.split(root)
    if gparent:
        return '%s %s %s %s %s' % (gparent, os.sep, parent, os.sep, fname)
    elif parent:
        return '%s %s %s' % (parent, os.sep, fname)
    else:
        return fname


class ZCViewMainFrame(wx.Frame):

    def __init__(self, parent, title='Myotisoft ZCView'):
        wx.Frame.__init__(self, parent, title=title, size=(640,480))

        # Application State
        self.dirname = ''
        self.filename = ''
        self.is_compressed = False
        self.is_linear_scale = True

        self.plotpanel = None

        # Menu Bar
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        open_item = file_menu.Append(wx.ID_OPEN, '&Open', ' Open a zero-cross file')
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        about_item = file_menu.Append(wx.ID_ABOUT, '&About', ' Information about this program')
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, 'E&xit', ' Terminate this program')
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        menu_bar.Append(file_menu, '&File')
        self.SetMenuBar(menu_bar)

        # Nav Toolbar
        tool_bar = self.CreateToolBar()
        open_item = tool_bar.AddLabelTool(wx.ID_ANY, 'Open file',       wx.Bitmap('resources/icons/file-8x.png'), shortHelp='Open')
        self.Bind(wx.EVT_TOOL, self.on_open, open_item)
        tool_bar.AddSeparator()
        prev_dir  = tool_bar.AddLabelTool(wx.ID_ANY, 'Previous folder', wx.Bitmap('resources/icons/chevron-left-8x.png'),
                                          shortHelp='Prev folder', longHelp='Open the previous folder (or use the `{` key)')
        self.Bind(wx.EVT_TOOL, self.on_prev_dir, prev_dir)
        prev_file = tool_bar.AddLabelTool(wx.ID_ANY, 'Previous file',   wx.Bitmap('resources/icons/caret-left-8x.png'),
                                          shortHelp='Prev file', longHelp='Open the previous file in this folder (or use `[` key)')
        self.Bind(wx.EVT_TOOL, self.on_prev_file, prev_file)
        next_file = tool_bar.AddLabelTool(wx.ID_ANY, 'Next file',       wx.Bitmap('resources/icons/caret-right-8x.png'),
                                          shortHelp='Next file', longHelp='Open the next file in this folder (or use the `]` key)')
        self.Bind(wx.EVT_TOOL, self.on_next_file, next_file)
        next_dir  = tool_bar.AddLabelTool(wx.ID_ANY, 'Next folder',     wx.Bitmap('resources/icons/chevron-right-8x.png'),
                                          shortHelp='Next folder', longHelp='Open the next folder (or use the `}` key)')
        self.Bind(wx.EVT_TOOL, self.on_next_dir, next_dir)
        tool_bar.AddSeparator()
        toggle_compressed = tool_bar.AddLabelTool(wx.ID_ANY, 'Compressed view', wx.Bitmap('resources/icons/audio-spectrum-8x.png'),
                                                  shortHelp='Toggle compressed', longHelp='Toggle compressed view on/off (or use the `c` key)')
        self.Bind(wx.EVT_TOOL, self.on_compressed_toggle, toggle_compressed)

        #self.SetToolBar(tool_bar)
        tool_bar.Realize()

        # Status Bar
        self.statusbar = self.CreateStatusBar()

        # Key Bindings
        prev_file_id, next_file_id, prev_dir_id, next_dir_id = wx.NewId(), wx.NewId(), wx.NewId(), wx.NewId()
        compressed_id, scale_id = wx.NewId(), wx.NewId()
        self.Bind(wx.EVT_MENU, self.on_prev_file, id=prev_file_id)
        self.Bind(wx.EVT_MENU, self.on_next_file, id=next_file_id)
        self.Bind(wx.EVT_MENU, self.on_prev_dir,  id=prev_dir_id)
        self.Bind(wx.EVT_MENU, self.on_next_dir,  id=next_dir_id)
        self.Bind(wx.EVT_MENU, self.on_compressed_toggle, id=compressed_id)
        self.Bind(wx.EVT_MENU, self.on_scale_toggle, id=scale_id)
        a_table = wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, ord('['), prev_file_id),
            (wx.ACCEL_NORMAL, ord(']'), next_file_id),
            (wx.ACCEL_SHIFT,  ord('['), prev_dir_id),  # {
            (wx.ACCEL_SHIFT,  ord(']'), next_dir_id),  # }
            (wx.ACCEL_NORMAL, ord(' '), compressed_id),
            (wx.ACCEL_NORMAL, ord('l'), scale_id),
        ])
        self.SetAcceleratorTable(a_table)

    def on_about(self, event):
        log.debug('about: %s', event)
        dlg = wx.MessageDialog(self, 'A boring Zero-Cross Viewer!', 'About ZCView', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def on_exit(self, event):
        log.debug('exit: %s', event)
        self.Close(True)

    def on_open(self, event):
        log.debug('open: %s', event)
        dlg = wx.FileDialog(self, 'Choose a file', self.dirname, '', 'Anabat files|*.*|Anabat files|*.zc', wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetFilename()
            dirname = dlg.GetDirectory()
            log.debug('open: %s', os.path.join(dirname, filename))
            self.load_file(dirname, filename)
        dlg.Destroy()

    def on_prev_file(self, event):
        log.debug('prev_file: %s', event)
        files = [fname for fname in os.listdir(self.dirname) if fnmatch(fname, '*.??#') or fnmatch(fname.lower(), '*.zc')]
        i = files.index(self.filename)
        if i <= 0:
            return  # we're at the start of the list
        self.load_file(self.dirname, files[i-1])

    def on_next_file(self, event):
        log.debug('next_file: %s', event)
        files = [fname for fname in os.listdir(self.dirname) if fnmatch(fname, '*.??#') or fnmatch(fname.lower(), '*.zc')]
        i = files.index(self.filename)
        if i == len(files) - 1:
            return  # we're at the end of the list
        self.load_file(self.dirname, files[i+1])

    def on_prev_dir(self, event):
        log.debug('prev_dir: %s', event)
        parent, current = os.path.split(self.dirname)
        siblings = [p for p in os.listdir(parent) if os.path.isdir(os.path.join(parent, p))]
        i = siblings.index(current)
        if i <= 0:
            return  # we're at the start of the list
        newdir = os.path.join(parent, siblings[i-1])
        files = [fname for fname in os.listdir(newdir) if fnmatch(fname, '*.??#') or fnmatch(fname.lower(), '*.zc')]
        if not files:
            return  # no anabat files in next dir
        self.load_file(newdir, files[0])

    def on_next_dir(self, event):
        log.debug('next_dir: %s', event)
        parent, current = os.path.split(self.dirname)
        siblings = [p for p in os.listdir(parent) if os.path.isdir(os.path.join(parent, p))]
        i = siblings.index(current)
        if i == len(siblings) - 1:
            return  # we're at the end of the list
        newdir = os.path.join(parent, siblings[i+1])
        files = [fname for fname in os.listdir(newdir) if fnmatch(fname, '*.??#') or fnmatch(fname.lower(), '*.zc')]
        if not files:
            return  # no anabat files in next dir
        self.load_file(newdir, files[0])

    def load_file(self, dirname, filename):
        log.debug('load_file:  %s  %s', dirname, filename)
        path = os.path.join(dirname, filename)
        if not path:
            return
        times, freqs, metadata = extract_anabat(path)
        self.dirname, self.filename = dirname, filename  # only set on success
        log.debug('    %s:  times: %d  freqs: %d', filename, len(times), len(freqs))
        try:
            conf = dict(compressed=self.is_compressed, scale='linear' if self.is_linear_scale else 'log')
            panel = ZeroCrossPlotPanel(self, times, freqs, name=title_from_path(path), config=conf)
            panel.Show()
            self.statusbar.SetStatusText('%s     Dots: %5d     Fmin: %5.1fkHz     Fmax: %5.1fkHz'
                                         % (metadata.get('timestamp', None) or metadata.get('date', ''),
                                            len(freqs), min(f for f in freqs if f >= 100)/1000.0, max(freqs)/1000.0))
            if self.plotpanel:
                self.plotpanel.Destroy()
            self.plotpanel = panel
        except Exception, e:
            log.exception('Failed plotting %s', filename)

    def on_compressed_toggle(self, event):
        log.debug('toggling compressed view (%s)', not self.is_compressed)
        self.is_compressed = not self.is_compressed
        if not self.filename:
            return
        self.load_file(self.dirname, self.filename)

    def on_scale_toggle(self, event):
        log.debug('toggling Y scale (%s)', 'linear' if self.is_linear_scale else 'log')
        self.is_linear_scale = not self.is_linear_scale
        self.load_file(self.dirname, self.filename)


class PlotPanel(wx.Panel):
    """Base class for embedding matplotlib in wx.

    The PlotPanel has a Figure and a Canvas. OnSize events simply set a
    flag, and the actual resizing of the figure is triggered by an Idle event.
    See: http://wiki.scipy.org/Matplotlib_figure_in_a_wx_panel
    """

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
        self.figure = Figure(None, dpi)
        self.canvas = FigureCanvasWxAgg(self, -1, self.figure)
        self.SetColor(color)

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
        self.SetSize(pixels)
        self.canvas.SetSize(pixels)
        self.figure.set_size_inches( float(pixels[0])/self.figure.get_dpi(), float(pixels[1])/self.figure.get_dpi() )

    def draw(self):
        pass  # abstract, to be overridden by child classes


def slopes(x, y):
    """
    Produce an array of slope values in octaves per second.
    We very, very crudely try to compensate for the jump between pulses, but don't deal well with noise.
    :param x:
    :param y:
    :return:
    """
    if not x or not y:
        return []
    elif len(x) == 1:
        return [0.0]
    slopes = []
    px, py = x[0], math.log(y[0], 2)
    s = 0.0
    for x, y in zip(x[1:], [math.log(f, 2) for f in y[1:]]):
        dx = x - px
        dy = py - y  # yes, we invert negative to positive slope
        slope = dy / dx
        if slope > -5000:
            slopes.append(slope)
        else:
            slopes.append(slopes[-1] if slopes else 0.0)  # big jumps from end of pulse to start of next pulse
        px, py = x, y
    slopes.append(slopes[-1])  # hack for final lonely dot
    return slopes


class ZeroCrossPlotPanel(PlotPanel):

    config = {
        'freqminmax': (15, 100),
        'scale': 'linear',         # linear | log
        'markers': (25, 40),
        'dotcolor': 'b',
        'dotmarker': '.',
        'dotsize': 5,
        'compressed': False,
    }

    def __init__(self, parent, times, freqs, config=None, **kwargs):
        self.times = times if times else [0.0]
        self.freqs = freqs if freqs else [0.0]
        self.slopes = slopes(self.times, self.freqs)
        #log.debug(', '.join('%0.1f'%s for s in sorted(self.slopes)))
        log.debug('Smax: %s  Smin: %s  Sc: ?', max(self.slopes), min(self.slopes))
        self.freqs = [freq / 1000.0 for freq in freqs]  # convert Hz to KHz
        self.name = kwargs.get('name', '')
        if config:
            self.config.update(config)
        PlotPanel.__init__(self, parent) #, **kwargs)
        self.SetColor((0xff, 0xff, 0xff))

    def draw(self):
        if not hasattr(self, 'subplot'):
            self.subplot = self.figure.add_subplot(111)

        miny, maxy = self.config['freqminmax']
        plot_kwargs = dict(cmap='jet', vmin=0, vmax=1000, linewidths=0.0)
        # TODO: neither of these are proper compressed or non-compressed views!
        if self.config['compressed']:
            self.subplot.scatter(self.times, self.freqs, c=self.slopes, **plot_kwargs)
            self.subplot.set_xlim(self.times[0], self.times[-1])
            self.subplot.set_xlabel('Time (sec)')
        else:
            x = range(len(self.freqs))
            self.subplot.scatter(x, self.freqs, c=self.slopes, **plot_kwargs)
            self.subplot.set_xlim(0, len(x))
            self.subplot.set_xlabel('Dot Count')

        self.subplot.set_title(self.name)
        self.subplot.set_yscale(self.config['scale'])
        self.subplot.set_ylim(miny, maxy)
        self.subplot.set_ylabel('Frequency (KHz)')
        self.subplot.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        minytick = miny if miny % 10 == 0 else miny + 10 - miny % 10
        maxytick = maxy if maxy % 10 == 0 else maxy + 10 - maxy % 10
        ticks = range(minytick, maxytick+1, 10)   # labels every 10kHz
        log.debug(ticks)
        self.subplot.get_yaxis().set_ticks(ticks)
        self.subplot.grid(axis='y', which='both')
        for freqk in self.config['markers']:
            self.subplot.axhline(freqk, color='r')
