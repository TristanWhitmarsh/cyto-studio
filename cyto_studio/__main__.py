"""
cyto-studio reads zarr files and displays them
"""
# import sys

try:
    from cyto_studio.n_space import CYTOSTUDIO
except:
    from cyto_studio import CYTOSTUDIO

def main():
    napari = CYTOSTUDIO()
    napari.main()

if __name__ == "__main__":
    main()