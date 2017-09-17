from configparser import ConfigParser, NoOptionError
from srctools import AtomicWriter, Property
import utils

__all__ = [
    'option_handler', 'get_curr_settings', 'apply_settings',
    'ConfigFile', 'NoOptionError', 'GEN_OPTS',
]

LOGGER = utils.getLogger(__name__)

# Functions for saving or loading application settings.
# Call with a block to load, or with no args to return the current
# values.
option_handler = utils.FuncLookup('OptionHandlers')


def get_curr_settings() -> Property:
    """Return a property tree defining the current options."""
    props = Property('', [])

    for opt_id, opt_func in option_handler.items():
        opt_prop = opt_func()
        opt_prop.name = opt_id.title()
        props.append(opt_prop)

    return props


def apply_settings(props: Property):
    """Given a property tree, apply it to the widgets."""
    for opt_prop in props:
        try:
            func = option_handler[opt_prop.name]
        except KeyError:
            LOGGER.warning('No handler for option type "{}"!', opt_prop.real_name)
        else:
            func(opt_prop)


class ConfigFile(ConfigParser):
    """A version of ConfigParser which can easily save itself.

    The config will track whether any values change, and only resave
    if modified.
    get_val, get_bool, and get_int are modified to return defaults instead
    of erroring.
    """
    def __init__(self, filename, *, in_conf_folder=True, auto_load=True):
        """Initialise the config file.

        `filename` is the name of the config file, in the `root` directory.
        If `auto_load` is true, this file will immediately be read and parsed.
        If in_conf_folder is set, The folder is relative to the 'config/'
        folder in the BEE2 folder.
        """
        super().__init__()

        self.has_changed = False

        if filename is not None:
            if in_conf_folder:
                self.filename = utils.conf_location('config/' + filename)
            else:
                self.filename = filename

            self.writer = AtomicWriter(self.filename)
            self.has_changed = False

            if auto_load:
                self.load()
        else:
            self.filename = self.writer = None

    def load(self):
        if self.filename is None:
            return

        try:
            with open(self.filename, 'r') as conf:
                self.read_file(conf)
        except (FileNotFoundError, IOError):
            LOGGER.warning(
                'Config "{}" not found! Using defaults...',
                self.filename,
            )
            # If we fail, just continue - we just use the default values
        # We're not different to the file on disk..
        self.has_changed = False

    def save(self):
        """Write our values out to disk."""
        LOGGER.info('Saving changes in config "{}"!', self.filename)
        if self.filename is None:
            raise ValueError('No filename provided!')

        with self.writer as conf:
            self.write(conf)
        self.has_changed = False

    def save_check(self):
        """Check to see if we have different values, and save if needed."""
        if self.has_changed:
            self.save()

    def set_defaults(self, def_settings):
        """Set the default values if the settings file has no values defined."""
        for sect, values in def_settings.items():
            if sect not in self:
                self[sect] = {}
            for key, default in values.items():
                if key not in self[sect]:
                    self[sect][key] = str(default)
        self.save_check()

    def get_val(self, section: str, value: str, default: str) -> str:
        """Get the value in the specifed section.

        If either does not exist, set to the default and return it.
        """
        if section not in self:
            self[section] = {}
        if value in self[section]:
            return self[section][value]
        else:
            self.has_changed = True
            self[section][value] = default
            return default

    def __getitem__(self, section):
        try:
            return super().__getitem__(section)
        except KeyError:
            self[section] = {}
            return super().__getitem__(section)


    def getboolean(self, section, value, default=False) -> bool:
        """Get the value in the specified section, coercing to a Boolean.

            If either does not exist, set to the default and return it.
            """
        if section not in self:
            self[section] = {}
        try:
            return super().getboolean(section, value)
        except (ValueError, NoOptionError):
            #  Invalid boolean, or not found
            self.has_changed = True
            self[section][value] = str(int(default))
            return default

    get_bool = getboolean

    def getint(self, section, value, default=0) -> int:
        """Get the value in the specified section, coercing to a Integer.

            If either does not exist, set to the default and return it.
            """
        if section not in self:
            self[section] = {}
        try:
            return super().getint(section, value)
        except (ValueError, NoOptionError):
            self.has_changed = True
            self[section][value] = str(int(default))
            return default

    get_int = getint

    def add_section(self, section):
        self.has_changed = True
        super().add_section(section)

    def remove_section(self, section):
        self.has_changed = True
        super().remove_section(section)

    def set(self, section, option, value=None):
        orig_val = self.get(section, option, fallback=None)
        value = str(value)
        if orig_val is None or orig_val != value:
            self.has_changed = True
            super().set(section, option, value)

    add_section.__doc__ = ConfigParser.add_section.__doc__
    remove_section.__doc__ = ConfigParser.remove_section.__doc__
    set.__doc__ = ConfigParser.set.__doc__


# Define this here so app modules can easily acess the config
# Don't load it though, since this is imported by VBSP too.
GEN_OPTS = ConfigFile('config.cfg', auto_load=False)
