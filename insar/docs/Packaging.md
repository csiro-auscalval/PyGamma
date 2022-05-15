## Product packaging

Once the user has processed a stack, it's often desirable they can distribute that data to others in a standard format.
`gamma_insar` provides a packaging script which will export a stack's data as an (ODC)[https://github.com/opendatacube/datacube-core] dataset via (eodatasets)[https://github.com/opendatacube/eo-datasets] which allows users to distribute the stack as an Open Data Cube for users to easily analyse and produce higher level products upon.

The process is incredibly simple, as this example shows, the packaging of a backscatter for a specific Sentinel-1 track/frame:

```BASH
package \
    --track T133D --frame F35S \
    --input-dir /path/to/workflow_output_data \
    --pkgdir /path/to/track_frame_pkg_output \
    --error-on-existing
```

Note: We recommend using `--error-on-existing` by default to ensure you don't accidentally over-write existing data that you're packaging.

Additional options exist for handling various production scenarios - some of these are covered in sections below, however please refer to `package --help` for further details.

# Re-packaging missing products

If the user already has a set of packaged data they want to update with new data that did *not* previously exist, they can do so in much the same way they package data normally but with the flag `--overwrite-existing`.  This flag will essentially skip packaging of any data that already exists, and thus only package data which has not yet been packaged.

If the original script above was used to package your data, re-running it with this flag would produce an identical packaged product with updated timestamps:

```BASH
package \
    --track T133D --frame F35S \
    --input-dir /path/to/workflow_output_data \
    --pkgdir /path/to/track_frame_pkg_output \
    --overwrite-existing
```

# Re-packacing existing products

If the user already has a set of packaged data they want to update with new data that *already exists*, they can do so in much the same way they package data normally but *without* the `--error-on-existing` flag from the original example.  Without this flag, by default the packaging script will happily over-write
