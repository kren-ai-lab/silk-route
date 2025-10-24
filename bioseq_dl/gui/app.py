import gradio as gr
from bioseq_dl.gui.main_ui import build_ui

"""
Gradio app for BioSeqDownloader

Run with:
    bioseq-dl gui run

"""
# Building the main UI in as global variable
# Makes it easier to launch gradio with the reload mode, using
# gradio bioseq_dl/gui/app.py --watch-dirs bioseq_dl/gui,bioseq_dl/core
demo = build_ui()

def main(host="127.0.0.1", port=7860, share=False):
    demo.launch(server_name=host, server_port=port, share=share)


if __name__ == "__main__":
    main()