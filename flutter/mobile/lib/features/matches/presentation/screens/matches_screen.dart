import 'package:flutter/material.dart';

class MatchesScreen extends StatelessWidget {
  const MatchesScreen({
    required this.groupId,
    super.key,
  });

  final String groupId;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: <Widget>[
        Text(
          'Partidos',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 8),
        Text(
          'El primer feature fuerte del MVP es el wizard de carga en 4 pasos.',
          style: Theme.of(context).textTheme.bodyLarge,
        ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Wizard propuesto',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                const Text('1. Fecha, modalidad y cancha'),
                const Text('2. Armado de equipos'),
                const Text('3. Resultado final y goles'),
                const Text('4. Resumen y confirmación'),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () {},
                  child: const Text('Nuevo partido'),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const <Widget>[
                Text('Historial base'),
                SizedBox(height: 12),
                Text('Todavía no hay partidos cargados.'),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
