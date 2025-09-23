import gradio as gr
from .main_ui import build_ui

"""
Gradio app for BioSeqDownloader

Run with:
    bioseq-dl gui run

"""
def main(host="127.0.0.1", port=7860, share=False):
    demo = build_ui()
    demo.launch(server_name=host, server_port=port, share=share)

if __name__ == "__main__":
    main()