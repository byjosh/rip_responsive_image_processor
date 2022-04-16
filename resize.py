#!/usr/bin/env python3
# copyright josh - web@byjosh.co.uk

from pickletools import optimize
import sys
import os
import logging

from PIL import Image
from PIL import ImageOps
import begin
from sortedcontainers import SortedDict

# Done: take image, resize, do alt, generate sourceset, strip exif, output in separate folder
# TODO: sortedcontainers may be an unnecessary dependency due to stable insertion order in dictionaries after Python 3.7

# configure logger
logger = logging.getLogger("log")


def factor_scale(im, proportion):
    """
    Arguments:
    im - PIL Image object
    proportion - desired proportion greater than 0 less than 1 - image will be scaled in proportion
    Returns:
    (width,height) as integer tuple
    """
    if proportion < 1 and proportion > 0:
        return (int(im.size[0]*proportion), int(im.size[1]*proportion))
    else:
        logging.ERROR("proportion should be between 0 and 1")
        logging.ERROR("returning maximum size")
        return (int(im.size[0]), int(im.size[1]))


def height_scale(im, height):
    """
    Arguments:
    im - PIL Image object
    height - desired max height - image will be scaled in proportion
    Returns:
    (width,height) as integer tuple
    """

    if type(height) is int:
        factor = height / im.size[1]
        width = im.size[0] * factor
        return (int(width), int(height))
    else:
        logging.ERROR("height should be integer")
        logging.ERROR("returning maximum size")
        return (int(im.size[0]), int(im.size[1]))


def width_scale(im, width):
    """
    Arguments:
    im - PIL Image object
    width - desired max width - image will be scaled in proportion
    Returns:
    (width,height) as integer tuple
    """
    if type(width) is int:
        factor = width / im.size[0]
        height = im.size[1] * factor
        return (int(width), int(height))
    else:
        logging.ERROR("width should be integer")
        logging.ERROR("returning maximum size")
        return (int(im.size[0]), int(im.size[1]))


def find_new_size(im, proportion, height, width):
    """
    Arguments:
    proportion
    height
    width
    Return:
    Tuple of new size
    """

    if proportion != 0:
        target_size = factor_scale(im, proportion)
    elif height != 0:
        target_size = height_scale(im, height)
    elif width != 0:
        target_size = width_scale(im, width)
    return target_size


def sourceset_files_sizes(dict_sorted, dir):
    """
    TODO: can a sortedDict be discarded given insertion order stability in dictionaries since Python 3.7?
    Returns:
    dictionary of {width: "full_filename_at_that_width"}
    """
    output = ""

    for k in dict_sorted:
        output += '{} {}w,'.format(dir+dict_sorted[k], k)
    return output.strip(",")


def im_resize(im, originalfilename, target, viewwidth, breakpoint, alt, quality, lazy, dir):
    """
    Arguments:
    im - PIL Image object
    originalfilename - full file name with extension
    target - (width,height) integer tuple of target maximum size
    viewwidth - percentage of CSS view width vw that should be used in img tag - 100 for full width image
    breakpoint - used in responsive image tag - see note for main function
    alt - alt text that one can supply on command line if a single image but will be asked for if multiple images processed
    quality - jpeg quality set at 75 by default as for Pillow - but try lower for smaller images
    lazy - whether img should be lazy or eager loading
    dir - quoted string of where images are uploaded - ends with forward slash
    Returns:
    None - saves images and HTML img tag text as MD in current folder (different for each image)
    """
    # widths to save images at
    sizes = [200, 400, 600, 768, 960, 1024, 1440, 1920]
    # only use ones smaller than target size width
    new_sizes = [x for x in sizes if x < target[0]]
    srcset_dict = {}

    # create folder for output of each file
    filename = ".".join(originalfilename.split(".")[:-1])

    # if dir exists add appendix _v1,_v2 etc
    appendix = ""
    if os.path.isdir(filename):
        appendix = 1
        while os.path.isdir(filename+"_v"+str(appendix)):
            appendix += 1
        appendix = "_v" + str(appendix)

    newdir = filename+appendix
    os.mkdir(newdir)
    os.chdir(newdir)
    logger.debug("Current working directory is: {}".format(os.getcwd()))

    def save_img(im, this_size):
        new_dimensions = "_{}x{}".format(this_size[0], this_size[1])
        out = im.resize(this_size)
        rename = originalfilename.split(".")
        this_file = "".join(rename[0:-1]) + \
            new_dimensions + "." + str(rename[-1])
        srcset_dict[this_size[0]] = this_file
        logger.debug("current filename is: {}".format(this_file))
        # added quality for JPEGs and optimize for PNGs
        if str(rename[-1]) in ["JPG", "JPEG", "jpeg", "jpg"]:
            out.save(this_file, quality=quality, progessive=True)
        elif str(rename[-1]) in ["PNG", "png"]:
            out.save(this_file, compress_level=9, exif="")
        with Image.open(this_file) as img:
            logger.debug("About to do EXIF transpose")
            im = ImageOps.exif_transpose(img)
            logger.info("Saved EXIF: {}".format(img.getexif()))

    for s in new_sizes:
        current_size = width_scale(im, s)
        save_img(im, current_size)
    # save in target size - biggest
    save_img(im, target)
    logger.debug("Source set dictionary: {}".format(srcset_dict))
    srcset_sorted = SortedDict(srcset_dict)
    final_item_key = list(srcset_sorted.keys())[-1]
    logger.debug("Sorted source set dictionary: {}".format(srcset_sorted))
    if breakpoint > 0:
        breakpoint_width = int(viewwidth * 0.5)
        sizes = "(min-width: {}px) {}vw, {}vw".format(int(breakpoint),
                                                      breakpoint_width, viewwidth)
    elif breakpoint <= 0:
        sizes = "{}vw".format(viewwidth)
    srcset_html = '<img src="{}" srcset="{}" sizes="{}vw" alt="{}" loading="{}">'.format(
        srcset_sorted[final_item_key], sourceset_files_sizes(srcset_sorted, dir), viewwidth, alt, "lazy" if lazy == 1 else "eager")
    with open(os.path.split(os.getcwd())[1]+".md", mode="w") as file:
        file.write(srcset_html)
    logger.debug("Source set HTML: {}".format(srcset_html))
    # return to parent directory for next image
    os.chdir("../")
    logger.debug(os.getcwd())


@ begin.start(auto_convert=True)
def main(proportion=0.0, height=0, width=0, viewwidth=100, breakpoint=0, alt=None, quality=75, lazy_load=1, loglevel='INFO', dir="", * files):
    """
    all arguments can be supplied as short versions e.g. -p 0.5 to halve the image in proportion
    only 1 of p,h, or w needed - along with alt text

    Arguments:
    proportion - more than zero less than 1 - how much to scale image down by
    height - a target height in pixels
    width - a target width in pixels - only one of proportion, height or width needed
    viewwidth - CSS value 0 to 100 as percentage of viewport width used to select appropriate responsive image
    breakpoint - will be used to specify half of viewwidth in responsive image e.g. (min-width: 1024px) 50vw, 100vw
    alt - alt text - required but asked for if multiple images or not supplied
    quality - JPEG quality 0 - 100 but use 50 to 95 probably
    lazy_load - if 1 then HTML tag output into markdown file will have loading="lazy" set
    loglevel - development option of how much detail to show as program runs - 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    dir - quoted string of where images are uploaded - ends with forward slash
    files - one or more files to convert using these settings - dialogue will ask for individual alt text
    """
    logging.basicConfig(level=loglevel)
    logger.debug("args {}".format(sys.argv[1:]))
    logger.debug("File length: {}".format(len(files)))
    logger.debug("Alt text is None ? {}".format(alt == None))
    for infile in sys.argv[1:]:
        if os.path.isfile(infile):
            try:
                # test
                if((len(files) > 1) or (alt == None)):
                    print("For {}".format("".join(infile.split(".")[:-1])))
                    alt = input("type alt text: ")

                with Image.open(infile) as im:
                    # EXIF tags may mean file is displayed in portrait in browser yet without following op would save landscape images
                    logger.debug("About to do EXIF transpose")
                    im = ImageOps.exif_transpose(im)
                    logger.info("Original EXIF: {}".format(im.getexif()))
                    logger.debug("File: {}, im.format: {}, size: {}, mode: {}".format(
                        infile, im.format, im.size, im.mode))
                    logger.debug("proportion {} height {} width {}".format(
                        proportion, height, width))
                    target_size = find_new_size(im, proportion, height, width)

                    im_resize(im, infile, target_size,
                              viewwidth, breakpoint, alt, quality, lazy_load, dir)

            except OSError:
                pass
