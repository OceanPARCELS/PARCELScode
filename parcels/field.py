from scipy.interpolate import RegularGridInterpolator
from cachetools import cachedmethod, LRUCache
from collections import Iterable
from py import path
import numpy as np
import xray
import operator
from ctypes import Structure, c_int, c_float, c_double, POINTER
from netCDF4 import Dataset, num2date
from math import cos, pi
from datetime import timedelta


__all__ = ['CentralDifferences', 'Field', 'Geographic', 'GeographicPolar']


class FieldSamplingError(RuntimeError):
    """Utility error class to propagate erroneous field sampling"""

    def __init__(self, x, y, field=None):
        self.field = field
        self.x = x
        self.y = y
        message = "%s sampled at (%f, %f)" % (
            field.name if field else "Grid", self.x, self.y
        )
        super(FieldSamplingError, self).__init__(message)


class TimeExtrapolationError(RuntimeError):
    """Utility error class to propagate erroneous time extrapolation sampling"""

    def __init__(self, time, field=None):
        self.field = field
        self.time = time
        message = "%s sampled outside time domain at time %f." % (
            field.name if field else "Grid", self.time
        )
        message += " Try setting allow_time_extrapolation to True"
        super(TimeExtrapolationError, self).__init__(message)


def CentralDifferences(field_data, lat, lon):
    """Function to calculate gradients in two dimensions
    using central differences on field

    :param field_data: data to take the gradients of
    :param lat: latitude vector
    :param lon: longitude vector

    :rtype: gradient of data in zonal and meridional direction
    """
    r = 6.371e6  # radius of the earth
    deg2rd = np.pi / 180
    dy = r * np.diff(lat) * deg2rd
    # calculate the width of each cell, dependent on lon spacing and latitude
    dx = np.zeros([len(lon)-1, len(lat)], dtype=np.float32)
    for x in range(len(lon))[1:]:
        for y in range(len(lat)):
            dx[x-1, y] = r * np.cos(lat[y] * deg2rd) * (lon[x]-lon[x-1]) * deg2rd
    # calculate central differences for non-edge cells (with equal weighting)
    dVdx = np.zeros(shape=np.shape(field_data), dtype=np.float32)
    dVdy = np.zeros(shape=np.shape(field_data), dtype=np.float32)
    for x in range(len(lon))[1:-1]:
        for y in range(len(lat)):
            dVdx[x, y] = (field_data[x+1, y] - field_data[x-1, y]) / (2 * dx[x-1, y])
    for x in range(len(lon)):
        for y in range(len(lat))[1:-1]:
            dVdy[x, y] = (field_data[x, y+1] - field_data[x, y-1]) / (2 * dy[y-1])
    # Forward and backward difference for edges
    for x in range(len(lon)):
        dVdy[x, 0] = (field_data[x, 1] - field_data[x, 0]) / dy[0]
        dVdy[x, len(lat)-1] = (field_data[x, len(lat)-1] - field_data[x, len(lat)-2]) / dy[len(lat)-2]
    for y in range(len(lat)):
        dVdx[0, y] = (field_data[1, y] - field_data[0, y]) / dx[0, y]
        dVdx[len(lon)-1, y] = (field_data[len(lon)-1, y] - field_data[len(lon)-2, y]) / dx[len(lon)-2, y]

    return [dVdx, dVdy]


class UnitConverter(object):
    """ Interface class for spatial unit conversion during field sampling
        that performs no conversion.
    """
    source_unit = None
    target_unit = None

    def to_target(self, value, x, y):
        return value

    def ccode_to_target(self, x, y):
        return "1.0"

    def to_source(self, value, x, y):
        return value

    def ccode_to_source(self, x, y):
        return "1.0"


class Geographic(UnitConverter):
    """ Unit converter from geometric to geographic coordinates (m to degree) """
    source_unit = 'm'
    target_unit = 'degree'

    def to_target(self, value, x, y):
        return value / 1000. / 1.852 / 60.

    def ccode_to_target(self, x, y):
        return "(1.0 / (1000.0 * 1.852 * 60.0))"


class GeographicPolar(UnitConverter):
    """ Unit converter from geometric to geographic coordinates (m to degree)
        with a correction to account for narrower grid cells closer to the poles.
    """
    source_unit = 'm'
    target_unit = 'degree'

    def to_target(self, value, x, y):
        return value / 1000. / 1.852 / 60. / cos(y * pi / 180)

    def ccode_to_target(self, x, y):
        return "(1.0 / (1000. * 1.852 * 60. * cos(%s * M_PI / 180)))" % y


class Field(object):
    """Class that encapsulates access to field data.

    :param name: Name of the field
    :param data: 2D array of field data
    :param lon: Longitude coordinates of the field
    :param lat: Latitude coordinates of the field
    :param depth: Depth coordinates of the field
    :param time: Time coordinates of the field
    :param transpose: Transpose data to required (lon, lat) layout
    :param vmin: Minimum allowed value on the field.
           Data below this value are set to zero
    :param vmax: Maximum allowed value on the field
           Data above this value are set to zero
    :param time_origin: Time origin of the time axis
    :param units: type of units of the field (meters or degrees)
    :param interp_method: Method for interpolation
    :param allow_time_extrapolation: boolean whether to allow for extrapolation
    """

    def __init__(self, name, data, lon, lat, depth=None, time=None,
                 transpose=False, vmin=None, vmax=None, time_origin=0, units=None,
                 interp_method='linear', allow_time_extrapolation=None):
        self.name = name
        self.data = data
        self.lon = lon
        self.lat = lat
        self.depth = np.zeros(1, dtype=np.float32) if depth is None else depth
        self.time = np.zeros(1, dtype=np.float64) if time is None else time
        self.time_origin = time_origin
        self.units = units if units is not None else UnitConverter()
        self.interp_method = interp_method
        if allow_time_extrapolation is None:
            self.allow_time_extrapolation = True if time is None else False
        else:
            self.allow_time_extrapolation = allow_time_extrapolation

        # Ensure that field data is the right data type
        if not self.data.dtype == np.float32:
            print("WARNING: Casting field data to np.float32")
            self.data = self.data.astype(np.float32)
        if not self.lon.dtype == np.float32:
            print("WARNING: Casting lon data to np.float32")
            self.lon = self.lon.astype(np.float32)
        if not self.lat.dtype == np.float32:
            print("WARNING: Casting lat data to np.float32")
            self.lat = self.lat.astype(np.float32)
        if not self.time.dtype == np.float64:
            print("WARNING: Casting time data to np.float64")
            self.time = self.time.astype(np.float64)
        if transpose:
            # Make a copy of the transposed array to enforce
            # C-contiguous memory layout for JIT mode.
            self.data = np.transpose(self.data).copy()
        self.data = self.data.reshape((self.time.size, self.lat.size, self.lon.size))

        # Hack around the fact that NaN and ridiculously large values
        # propagate in SciPy's interpolators
        if vmin is not None:
            self.data[self.data < vmin] = 0.
        if vmax is not None:
            self.data[self.data > vmax] = 0.
        self.data[np.isnan(self.data)] = 0.

        # Variable names in JIT code
        self.ccode_data = self.name
        self.ccode_lon = self.name + "_lon"
        self.ccode_lat = self.name + "_lat"

        self.interpolator_cache = LRUCache(maxsize=2)
        self.time_index_cache = LRUCache(maxsize=2)

    @classmethod
    def from_netcdf(cls, name, dimensions, filenames, indices={},
                    allow_time_extrapolation=False, **kwargs):
        """Create field from netCDF file

        :param name: Name of the field to create
        :param dimensions: Variable names for the relevant dimensions
        :param filenames: Filenames of the field
        :param indices: indices for each dimension to read from file
        :param allow_time_extrapolation: boolean whether to allow for extrapolation
        """

        if not isinstance(filenames, Iterable):
            filenames = [filenames]
        with FileBuffer(filenames[0], dimensions) as filebuffer:
            lon, indslon = filebuffer.read_dimension('lon', indices)
            lat, indslat = filebuffer.read_dimension('lat', indices)
            # Assign time_units if the time dimension has units and calendar
            time_units = filebuffer.time_units
            calendar = filebuffer.calendar
        # Default depth to zeros until we implement 3D grids properly
        depth = np.zeros(1, dtype=np.float32)
        # Concatenate time variable to determine overall dimension
        # across multiple files
        timeslices = []
        for fname in filenames:
            with FileBuffer(fname, dimensions) as filebuffer:
                timeslices.append(filebuffer.time)
        timeslices = np.array(timeslices)
        time = np.concatenate(timeslices)
        if time_units is None:
            time_origin = 0
        else:
            time_origin = num2date(0, time_units, calendar)

        # Pre-allocate grid data before reading files into buffer
        data = np.empty((time.size, 1, lat.size, lon.size), dtype=np.float32)
        tidx = 0
        for tslice, fname in zip(timeslices, filenames):
            with FileBuffer(fname, dimensions) as filebuffer:
                filebuffer.indslat = indslat
                filebuffer.indslon = indslon
                data[tidx:(tidx+len(tslice)), 0, :, :] = filebuffer.data[:, :, :]
            tidx += len(tslice)
        # Time indexing after the fact only
        if 'time' in indices:
            time = time[indices['time']]
            data = data[indices['time'], :, :, :]
        return cls(name, data, lon, lat, depth=depth, time=time,
                   time_origin=time_origin, allow_time_extrapolation=allow_time_extrapolation, **kwargs)

    def __getitem__(self, key):
        return self.eval(*key)

    def gradient(self, timerange=None, lonrange=None, latrange=None, name=None):
        """Method to create gradients of Field"""
        if name is None:
            name = 'd' + self.name

        if timerange is None:
            time_i = range(len(self.time))
            time = self.time
        else:
            time_i = range(np.where(self.time >= timerange[0])[0][0], np.where(self.time <= timerange[1])[0][-1]+1)
            time = self.time[time_i]
        if lonrange is None:
            lon_i = range(len(self.lon))
            lon = self.lon
        else:
            lon_i = range(np.where(self.lon >= lonrange[0])[0][0], np.where(self.lon <= lonrange[1])[0][-1]+1)
            lon = self.lon[lon_i]
        if latrange is None:
            lat_i = range(len(self.lat))
            lat = self.lat
        else:
            lat_i = range(np.where(self.lat >= latrange[0])[0][0], np.where(self.lat <= latrange[1])[0][-1]+1)
            lat = self.lat[lat_i]

        dVdx = np.zeros(shape=(time.size, lat.size, lon.size), dtype=np.float32)
        dVdy = np.zeros(shape=(time.size, lat.size, lon.size), dtype=np.float32)
        for t in np.nditer(np.int32(time_i)):
            grad = CentralDifferences(np.transpose(self.data[t, :, :][np.ix_(lat_i, lon_i)]), lat, lon)
            dVdx[t, :, :] = np.array(np.transpose(grad[0]))
            dVdy[t, :, :] = np.array(np.transpose(grad[1]))

        return([Field(name + '_dx', dVdx, lon, lat, self.depth, time),
                Field(name + '_dy', dVdy, lon, lat, self.depth, time)])

    @cachedmethod(operator.attrgetter('interpolator_cache'))
    def interpolator2D(self, t_idx):
        """Provide a cached SciPy interpolator for spatial interpolation

        Note that the interpolator is configured to return NaN for
        out-of-bounds coordinates.
        """
        return RegularGridInterpolator((self.lat, self.lon), self.data[t_idx, :],
                                       bounds_error=False, fill_value=np.nan,
                                       method=self.interp_method)

    def temporal_interpolate_fullfield(self, tidx, time):
        """Calculate the data of a field between two snapshots,
        using linear interpolation

        :param tidx: Index in time array associated with time (via :func:`time_index`)
        :param time: Time to interpolate to

        :rtype: Linearly interpolated field"""
        t0 = self.time[tidx]
        t1 = self.time[tidx+1]
        f0 = self.data[tidx, :]
        f1 = self.data[tidx+1, :]
        return f0 + (f1 - f0) * ((time - t0) / (t1 - t0))

    def spatial_interpolation(self, tidx, y, x):
        """Interpolate horizontal field values using a SciPy interpolator"""
        val = self.interpolator2D(tidx)((y, x))
        if np.isnan(val):
            # Detect Out-of-bounds sampling and raise exception
            raise FieldSamplingError(x, y, field=self)
        else:
            return val

    @cachedmethod(operator.attrgetter('time_index_cache'))
    def time_index(self, time):
        """Find the index in the time array associated with a given time

        Note that we normalize to either the first or the last index
        if the sampled value is outside the time value range.
        """
        if not self.allow_time_extrapolation and (time < self.time[0] or time > self.time[-1]):
            raise TimeExtrapolationError(time, field=self)
        time_index = self.time <= time
        if time_index.all():
            # If given time > last known grid time, use
            # the last grid frame without interpolation
            return len(self.time) - 1
        else:
            return time_index.argmin() - 1 if time_index.any() else 0

    def eval(self, time, x, y):
        """Interpolate field values in space and time.

        We interpolate linearly in time and apply implicit unit
        conversion to the result. Note that we defer to
        scipy.interpolate to perform spatial interpolation.
        """
        t_idx = self.time_index(time)
        if t_idx < len(self.time)-1 and time > self.time[t_idx]:
            f0 = self.spatial_interpolation(t_idx, y, x)
            f1 = self.spatial_interpolation(t_idx + 1, y, x)
            t0 = self.time[t_idx]
            t1 = self.time[t_idx + 1]
            value = f0 + (f1 - f0) * ((time - t0) / (t1 - t0))
        else:
            # Skip temporal interpolation if time is outside
            # of the defined time range or if we have hit an
            # excat value in the time array.
            value = self.spatial_interpolation(t_idx, y, x)

        return self.units.to_target(value, x, y)

    def ccode_eval(self, var, t, x, y):
        # Casting interp_methd to int as easier to pass on in C-code
        return "temporal_interpolation_linear(%s, %s, %s, %s, %s, %s, &%s, %s)" \
            % (x, y, "particle->xi", "particle->yi", t, self.name, var,
               self.interp_method.upper())

    def ccode_convert(self, _, x, y):
        return self.units.ccode_to_target(x, y)

    @property
    def ctypes_struct(self):
        """Returns a ctypes struct object containing all relevant
        pointers and sizes for this field."""

        # Ctypes struct corresponding to the type definition in parcels.h
        class CField(Structure):
            _fields_ = [('xdim', c_int), ('ydim', c_int),
                        ('tdim', c_int), ('tidx', c_int),
                        ('allow_time_extrapolation', c_int),
                        ('lon', POINTER(c_float)), ('lat', POINTER(c_float)),
                        ('time', POINTER(c_double)),
                        ('data', POINTER(POINTER(c_float)))]

        # Create and populate the c-struct object
        allow_time_extrapolation = 1 if self.allow_time_extrapolation else 0
        cstruct = CField(self.lon.size, self.lat.size, self.time.size, 0,
                         allow_time_extrapolation,
                         self.lon.ctypes.data_as(POINTER(c_float)),
                         self.lat.ctypes.data_as(POINTER(c_float)),
                         self.time.ctypes.data_as(POINTER(c_double)),
                         self.data.ctypes.data_as(POINTER(POINTER(c_float))))
        return cstruct

    def show(self, with_particles=False, animation=False, show_time=0, vmin=None, vmax=None):
        """Method to 'show' a :class:`Field` using matplotlib

        :param with_particles: Boolean whether particles are also plotted on Field
        :param animation: Boolean whether result is a single plot, or an animation
        :param show_time: Time at which to show the Field (only in single-plot mode)
        :param vmin: minimum colour scale (only in single-plot mode)
        :param vmax: maximum colour scale (only in single-plot mode)
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.animation as animation_plt
            from matplotlib import rc
        except:
            raise RuntimeError("Visualisation not possible: matplotlib not found!")

        if with_particles or (not animation):
            idx = self.time_index(show_time)
            if self.time.size > 1:
                data = np.squeeze(self.temporal_interpolate_fullfield(idx, show_time))
            else:
                data = np.squeeze(self.data)

            vmin = data.min() if vmin is None else vmin
            vmax = data.max() if vmax is None else vmax
            cs = plt.contourf(self.lon, self.lat, data,
                              levels=np.linspace(vmin, vmax, 256))
            cs.cmap.set_over('k')
            cs.cmap.set_under('w')
            cs.set_clim(vmin, vmax)
            plt.colorbar(cs)
            if not with_particles:
                plt.show()
        else:
            fig = plt.figure()
            ax = plt.axes(xlim=(self.lon[0], self.lon[-1]), ylim=(self.lat[0], self.lat[-1]))

            def animate(i):
                data = np.squeeze(self.data[i, :, :])
                cont = ax.contourf(self.lon, self.lat, data,
                                   levels=np.linspace(data.min(), data.max(), 256))
                return cont

            rc('animation', html='html5')
            anim = animation_plt.FuncAnimation(fig, animate, frames=np.arange(1, self.data.shape[0]),
                                               interval=100, blit=False)
            plt.close()
            return anim

    def add_periodic_halo(self, zonal, meridional, halosize=5):
        """Add a 'halo' to all Fields in a grid, through extending the Field (and lon/lat)
        by copying a small portion of the field on one side of the domain to the other.

        :param zonal: Create a halo in zonal direction (boolean)
        :param meridional: Create a halo in meridional direction (boolean)
        :param halosize: size of the halo (in grid points). Default is 5 grid points
        """
        if zonal:
            lonshift = (self.lon[-1] - 2 * self.lon[0] + self.lon[1])
            self.data = np.concatenate((self.data[:, :, -halosize:], self.data,
                                        self.data[:, :, 0:halosize]), axis=len(self.data.shape)-1)
            self.lon = np.concatenate((self.lon[-halosize:] - lonshift,
                                       self.lon, self.lon[0:halosize] + lonshift))
        if meridional:
            latshift = (self.lat[-1] - 2 * self.lat[0] + self.lat[1])
            self.data = np.concatenate((self.data[:, -halosize:, :], self.data,
                                        self.data[:, 0:halosize, :]), axis=len(self.data.shape)-2)
            self.lat = np.concatenate((self.lat[-halosize:] - latshift,
                                       self.lat, self.lat[0:halosize] + latshift))

    def write(self, filename, varname=None):
        """Write a :class:`Field` to a netcdf file

        :param filename: Basename of the file
        :param varname: Name of the field, to be appended to the filename"""
        filepath = str(path.local('%s%s.nc' % (filename, self.name)))
        if varname is None:
            varname = self.name
        # Derive name of 'depth' variable for NEMO convention
        vname_depth = 'depth%s' % self.name.lower()

        # Create DataArray objects for file I/O
        t, d, x, y = (self.time.size, self.depth.size,
                      self.lon.size, self.lat.size)
        nav_lon = xray.DataArray(self.lon + np.zeros((y, x), dtype=np.float32),
                                 coords=[('y', self.lat), ('x', self.lon)])
        nav_lat = xray.DataArray(self.lat.reshape(y, 1) + np.zeros(x, dtype=np.float32),
                                 coords=[('y', self.lat), ('x', self.lon)])
        vardata = xray.DataArray(self.data.reshape((t, d, y, x)),
                                 coords=[('time_counter', self.time),
                                         (vname_depth, self.depth),
                                         ('y', self.lat), ('x', self.lon)])
        # Create xray Dataset and output to netCDF format
        dset = xray.Dataset({varname: vardata}, coords={'nav_lon': nav_lon,
                                                        'nav_lat': nav_lat})
        dset.to_netcdf(filepath)


class FileBuffer(object):
    """ Class that encapsulates and manages deferred access to file data. """

    def __init__(self, filename, dimensions):
        self.filename = filename
        self.dimensions = dimensions  # Dict with dimension keyes for file data
        self.dataset = None

    def __enter__(self):
        self.dataset = Dataset(str(self.filename), 'r', format="NETCDF4")
        return self

    def __exit__(self, type, value, traceback):
        self.dataset.close()

    def read_dimension(self, dimname, indices):
        dim = getattr(self, dimname)
        inds = indices[dimname] if dimname in indices else range(dim.size)
        if not isinstance(inds, list):
            raise RuntimeError('Index for '+dimname+' needs to be a list')
        return dim[inds], inds

    @property
    def lon(self):
        lon = self.dataset[self.dimensions['lon']]
        return lon[0, :] if len(lon.shape) > 1 else lon[:]

    @property
    def lat(self):
        lat = self.dataset[self.dimensions['lat']]
        return lat[:, 0] if len(lat.shape) > 1 else lat[:]

    @property
    def data(self):
        if len(self.dataset[self.dimensions['data']].shape) == 3:
            return self.dataset[self.dimensions['data']][:, self.indslat, self.indslon]
        else:
            return self.dataset[self.dimensions['data']][:, 0, self.indslat, self.indslon]

    @property
    def time(self):
        if self.time_units is not None:
            dt = num2date(self.dataset[self.dimensions['time']][:],
                          self.time_units, self.calendar)
            dt -= num2date(0, self.time_units, self.calendar)
            return list(map(timedelta.total_seconds, dt))
        else:
            return self.dataset[self.dimensions['time']][:]

    @property
    def time_units(self):
        """ Derive time_units if the time dimension has units """
        try:
            return self.dataset[self.dimensions['time']].units
        except:
            try:
                return self.dataset[self.dimensions['time']].Unit
            except:
                return None

    @property
    def calendar(self):
        """ Derive calendar if the time dimension has calendar """
        try:
            return self.dataset[self.dimensions['time']].calendar
        except:
            return 'standard'
