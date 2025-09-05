## List of things to do

- [x] For alphafold, biodbnet, biogrid and brenda change print for typer.echo
- [x] For alphafold, biodbnet, biogrid and brenda make the id a parameter that doesnt require a -i flag
- [x] Add options in geneontology
- [x] Change output to output_file and do:
    ```python
    if output_file:
        results.to_csv(output_file, index=False)
        typer.echo(f"Results saved to {output_file}")
    else:
        typer.echo(results)
    ```
- [x] To maintain consistency, make a second revision of the code in interfaces.