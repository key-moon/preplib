## prerequisites

 - Install [patchelf](https://github.com/NixOS/patchelf)
    - in ubuntu: `apt install patchelf`

## usage

### patch with file
```sh
$ patchlibc /path/to/bin /path/to/libc.so.6 
```

```sh
$ patchlibc /path/to/bin /path/to/libc.so.6 
```


### 

```sh
$ patchlibc --libc libc.so.6 my-program
```

```sh
$ patchlibc --update-list
```

```sh
$ 
```

TODO: add support for other libraries (e.g. libc++.so)
